import subprocess
import torch
import json
from typing import Dict, Optional, Tuple

class GPUHealthCheck:
    @staticmethod
    def check_cuda_memory() -> Tuple[bool, Optional[str]]:
        """
        Check if CUDA memory can be accessed properly.
        Returns: (is_healthy: bool, error_message: Optional[str])
        """
        try:
            memory_info = torch.cuda.mem_get_info()
            return True, None
        except RuntimeError as e:
            return False, f"CUDA memory check failed: {str(e)}"
    
    @staticmethod
    def check_ecc_errors() -> Tuple[bool, Optional[str]]:
        """
        Check for ECC (Error Correction Code) errors on NVIDIA GPUs.
        Returns: (is_healthy: bool, error_message: Optional[str])
        """
        try:
            # Query ECC error counts using nvidia-smi
            cmd = [
                'nvidia-smi', 
                '--query-gpu=index,ecc.errors.corrected.aggregate.total,ecc.errors.uncorrected.aggregate.total', 
                '--format=csv,nounits,noheader'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse the output to check for ECC errors
            lines = result.stdout.strip().split('\n')
            for line in lines:
                values = line.strip().split(',')
                if len(values) >= 3:
                    gpu_index = values[0].strip()
                    corrected_errors = values[1].strip()
                    uncorrected_errors = values[2].strip()
                    
                    # Check if there are any uncorrected ECC errors
                    if uncorrected_errors != "N/A" and uncorrected_errors != "0":
                        return False, f"Uncorrectable ECC errors detected on GPU {gpu_index}: {uncorrected_errors}"
                    
                    # Check if there are many corrected ECC errors (potential warning sign)
                    if corrected_errors != "N/A" and corrected_errors.isdigit() and int(corrected_errors) > 1000:
                        return False, f"High number of corrected ECC errors on GPU {gpu_index}: {corrected_errors}"
            
            return True, None
            
        except subprocess.CalledProcessError as e:
            # This might happen if the GPU doesn't support ECC
            return True, "ECC error check not applicable or not supported"
        except Exception as e:
            return False, f"Error checking ECC status: {str(e)}"
            
    @staticmethod
    def get_nvidia_smi_info() -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Get detailed GPU information using nvidia-smi.
        Returns: (is_healthy: bool, error_message: Optional[str], gpu_info: Optional[Dict])
        """
        try:
            # Query using CSV format instead of JSON
            cmd = [
                'nvidia-smi',
                '--query-gpu=timestamp,name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used',
                '--format=csv,nounits,noheader'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse CSV output into a dictionary
            gpus_info = []
            lines =  result.stdout.strip().split('\n')
            for line in lines:
                values = line.strip().split(',')
                gpu_info = {
                    'gpu': [{
                        'timestamp': values[0].strip(),
                        'name': values[1].strip(),
                        'temperature.gpu': float(values[2]),
                        'utilization.gpu': float(values[3]),
                        'utilization.memory': float(values[4]),
                        'memory.total': float(values[5]),
                        'memory.free': float(values[6]),
                        'memory.used': float(values[7])
                    }]
                }
                gpus_info.append(gpu_info)

                # Check for critical issues
                for gpu in gpu_info['gpu']:
                    if gpu['temperature.gpu'] > 85:
                        return False, f"GPU temperature too high: {gpu['temperature.gpu']}°C", gpus_info

                    if gpu['utilization.memory'] > 95:
                        return False, f"Memory utilization too high: {gpu['utilization.memory']}%", gpus_info
                

            return True, None, gpus_info

        except subprocess.CalledProcessError as e:
            return False, f"nvidia-smi command failed: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error during nvidia-smi check: {str(e)}", None

    @staticmethod
    def run_basic_cuda_test() -> Tuple[bool, Optional[str]]:
        """
        Run a basic CUDA operation to test GPU functionality.
        Returns: (is_healthy: bool, error_message: Optional[str])
        """
        try:
            # Try to perform a simple CUDA operation
            if torch.cuda.is_available():
                x = torch.rand(1000, 1000, device='cuda')
                y = torch.matmul(x, x)
                del x, y
                torch.cuda.empty_cache()
                return True, None
            else:
                return False, "CUDA is not available"
        except Exception as e:
            return False, f"Basic CUDA test failed: {str(e)}"

    @classmethod
    def check_gpu_health(cls) -> Tuple[bool, list[str]]:
        """
        Run all GPU health checks.
        Returns: (is_healthy: bool, list_of_errors: list[str])
        """
        errors = []
        
        # Check CUDA memory
        mem_healthy, mem_error = cls.check_cuda_memory()
        if not mem_healthy:
            errors.append(mem_error)

        # Check nvidia-smi info
        smi_healthy, smi_error, gpu_info = cls.get_nvidia_smi_info()
        if not smi_healthy:
            errors.append(smi_error)

        # Check for ECC errors
        ecc_healthy, ecc_error = cls.check_ecc_errors()
        if not ecc_healthy:
            errors.append(ecc_error)

        # Run basic CUDA test
        cuda_healthy, cuda_error = cls.run_basic_cuda_test()
        if not cuda_healthy:
            errors.append(cuda_error)

        return len(errors) == 0, errors
