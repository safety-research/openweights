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
    def get_nvidia_smi_info() -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Get detailed GPU information using nvidia-smi.
        Returns: (is_healthy: bool, error_message: Optional[str], gpu_info: Optional[Dict])
        """
        try:
            # Query multiple important parameters
            cmd = [
                'nvidia-smi', 
                '--query-gpu=timestamp,name,pci.bus_id,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used,power.draw,enforced.power.limit,fan.speed,clocks.current.sm,clocks.current.memory,ecc.mode.current,temperature.memory',
                '--format=json'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            gpu_info = json.loads(result.stdout)

            # Check for critical issues
            for gpu in gpu_info['gpu']:
                # Temperature check (threshold can be adjusted)
                if float(gpu['temperature.gpu']) > 85:
                    return False, f"GPU temperature too high: {gpu['temperature.gpu']}°C", gpu_info

                # Memory utilization check
                if float(gpu['utilization.memory']) > 95:
                    return False, f"Memory utilization too high: {gpu['utilization.memory']}%", gpu_info

                # ECC status check if available
                ecc_mode = gpu.get('ecc.mode.current')
                if ecc_mode and ecc_mode.lower() != 'enabled':
                    return False, f"ECC is not enabled: {ecc_mode}", gpu_info

            return True, None, gpu_info

        except subprocess.CalledProcessError as e:
            return False, f"nvidia-smi command failed: {str(e)}", None
        except json.JSONDecodeError as e:
            return False, f"Failed to parse nvidia-smi output: {str(e)}", None
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

        # Run basic CUDA test
        cuda_healthy, cuda_error = cls.run_basic_cuda_test()
        if not cuda_healthy:
            errors.append(cuda_error)

        return len(errors) == 0, errors
