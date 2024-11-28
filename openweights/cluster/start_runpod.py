"""
Usage:
    python start_runpod.py --gpu A6000 --container_disk_in_gb 25 --volume_in_gb 30

Note: possible unknown error with echo when running the script.
"""
import time
import os
import paramiko
from scp import SCPClient
import runpod
import os
from dotenv import load_dotenv
import fire
import backoff
import uuid

load_dotenv(override=True) 

runpod.api_key = os.environ.get("RUNPOD_API_KEY")
IMAGES = {
    'inference': 'nielsrolf/ow-inference',
    'finetuning': 'nielsrolf/ow-unsloth',
    'torch':  'runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04'
}
DOT_ENV_PATH = os.path.join(os.path.dirname(__file__), '../../.env')
TEMPLATE_ID = 'nqj8muhb8p'

GPUs = {
    'A6000': 'NVIDIA RTX 6000 Ada Generation',
    'A100': 'NVIDIA A100 80GB PCIe',
    'A100S': 'NVIDIA A100-SXM4-80GB',
    'H100': 'NVIDIA H100 PCIe',
    'H100N': 'NVIDIA H100 NVL',
}
GPU_COUNT = 1
allowed_cuda_versions = ['12.4']

def wait_for_pod(pod):
    while pod.get('runtime') is None:
        time.sleep(1)
        pod = runpod.get_pod(pod['id'])
    return pod

def get_ip_and_port(pod_id):
    ip, port = None, None
    while ip is None:
        pod = runpod.get_pod(pod_id)
        for ip_and_port in pod['runtime']['ports']:
            if ip_and_port['privatePort'] == 22:
                ip = ip_and_port['ip']
                port = ip_and_port['publicPort']
                return ip, port
        print('Waiting for pod to get IP address')
        time.sleep(1)
    

def create_ssh_client(pod):
    key_file = os.path.expanduser('~/.ssh/id_ed25519')
    user='root'
    ip, port = get_ip_and_port(pod['id'])
    print(f'Connecting to {ip}:{port}')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for _ in range(10):
        try:
            ssh.connect(ip, port=port, username=user, key_filename=key_file)
            return ssh
        except Exception as e:
            print(e)
            time.sleep(1)
            continue
    print('Failed to connect to pod. Shutting down pod')
    shutdown_pod(pod) 

def copy_to_pod(pod, src, dst):
    if not os.path.exists(src):
        # Assume src is relative to __file__
        src = os.path.join(os.path.dirname(__file__), src)
        assert os.path.exists(src), f"File {src} does not exist"
    ssh = create_ssh_client(pod)
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(src, dst)

def run_on_pod(pod, cmd):
    ssh = create_ssh_client(pod)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end='')

    while True:
        error_line = stderr.readline()
        if not error_line:
            break
        print(error_line, end='')

    stdin.close()
    stdout.close()
    stderr.close()
    ssh.close()

def run_on_pod_interactive(pod, cmd):
    ssh = create_ssh_client(pod)
    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.exec_command(cmd)
    output_buffer = b''
    logs = ''

    while True:
        if channel.recv_ready():
            output_buffer += channel.recv(1024)
            try:
                output = output_buffer.decode()
                print(output, end='')
                logs += output
                output_buffer = b''
                if "password" in output.lower():  # Check for password prompt or other interactive input requests
                    password = input("Enter the required input: ")
                    channel.send(password + '\n')
            except UnicodeDecodeError:
                pass  # Ignore decode errors and continue receiving data

        if channel.recv_stderr_ready():
            error = channel.recv_stderr(1024).decode(errors='ignore')
            print(error, end='')

        if channel.exit_status_ready():
            break

    channel.close()
    ssh.close()
    return logs
    


def check_correct_cuda(pod, allowed=allowed_cuda_versions):
    cmd = 'nvidia-smi'
    logs = run_on_pod_interactive(pod, cmd)
    return any([f'CUDA Version: {i}' in logs for i in allowed])



class ShutdownException(Exception):
    pass


def shutdown_pod(pod):
    runpod.terminate_pod(pod['id'])
    raise ShutdownException()



@backoff.on_exception(backoff.expo, Exception, max_time=60, max_tries=5)
def start_worker(gpu, image, count=GPU_COUNT, name=None, container_disk_in_gb=500, volume_in_gb=500, worker_id=None, dev_mode=False, pending_workers=None):
    gpu = GPUs.get(gpu, gpu)
    # default name: <username>-worker-<timestamp>
    name = name or f"{os.environ['USER']}-worker-{int(time.time())}"
    image = IMAGES.get(image, image)

    if pending_workers is None:
        pending_workers = []
    while True:
        try:
            if worker_id is None:
                worker_id = uuid.uuid4().hex[:8]
            pod = runpod.create_pod(
                name, image, gpu,
                container_disk_in_gb=container_disk_in_gb,
                volume_in_gb=volume_in_gb,
                volume_mount_path='/workspace',
                gpu_count=count,
                allowed_cuda_versions=allowed_cuda_versions,
                template_id=TEMPLATE_ID,
                ports="8000/http,22/tcp",
                start_ssh=True,
                env={
                    'WORKER_ID': worker_id,
                    'DOCKER_IMAGE': image,
                    'OW_DEV': 'true' if dev_mode else 'false'
                }
            )
            pending_workers.append(pod['id'])
            pod = wait_for_pod(pod)
            
            if not check_correct_cuda(pod):
                shutdown_pod(pod)
            
            pending_workers.remove(pod['id'])
            if dev_mode:
                ip, port = get_ip_and_port(pod['id'])
                return f"ssh root@{ip} -p {port} -i ~/.ssh/id_ed25519"
            else:
                return pod
        except ShutdownException:
            pending_workers.remove(pod['id'])
            continue

if __name__ == '__main__':
    fire.Fire(start_worker)