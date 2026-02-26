import subprocess
import json
import os
import threading
import time
import tempfile
import logging

class WorkerPool:
    def __init__(self, config_manager, base_dir):
        self.config_manager = config_manager
        self.base_dir = base_dir
        self.workers = {} # {library_name: process}
        self.worker_stderr_files = {} # {library_name: (file_handle, file_path)}
        self.worker_stats = {} # {library_name: {'last_used': time.time(), 'active_requests': 0}}
        self.lock = threading.Lock()
        self.request_id_counter = 1
        self._shutdown_event = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._cleanup_workers, daemon=True)
        self._cleanup_thread.start()

    def get_worker(self, library_name):
        """
        Ensures a worker for the given library is running and returns it.
        Returns (proc, resolved_name)
        """
        lib_conf = self.config_manager.get_library_config(library_name)
        if not lib_conf:
            logging.debug(f"get_worker returning error 'Library '{library_name}' not found in configuration.'")
            raise ValueError(f"Library '{library_name}' not found in configuration.")
            
        # If library_name was None (default), use the name from the found config
        # This ensures we store it under its real name key
        resolved_name = lib_conf.get("name", library_name or "default")
        lib_path = lib_conf["path"]

        with self.lock:
            proc = self.workers.get(resolved_name)
            if proc is None or proc.poll() is not None:
                # Clean up old stderr file if it exists
                if resolved_name in self.worker_stderr_files:
                    old_file, old_path = self.worker_stderr_files[resolved_name]
                    try:
                        old_file.close()
                    except:
                        pass
                    # Only delete if it's a temporary file (not a user log)
                    if old_path.startswith(tempfile.gettempdir()):
                        try:
                            os.remove(old_path)
                        except:
                            pass
                    del self.worker_stderr_files[resolved_name]
                
                # Start the worker
                current_dir = os.path.dirname(os.path.abspath(__file__))
                worker_path = os.path.join(current_dir, "worker.py")
                
                try:
                    # Check if worker logging is enabled
                    enable_logging = self.config_manager.get_global_setting("enable_worker_logging", False)
                    
                    if enable_logging:
                        # Create logs directory if it doesn't exist
                        log_dir = os.path.join(os.path.dirname(self.base_dir), "logs")
                        os.makedirs(log_dir, exist_ok=True)
                        log_file_path = os.path.join(log_dir, f"worker_{resolved_name}_stderr.log")
                        
                        # Open log file in append mode with line buffering
                        log_file = open(log_file_path, "a", encoding="utf-8", buffering=1)
                        log_file.write(f"\n--- Worker Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    else:
                        # Create a temporary file for stderr capture (for error extraction)
                        log_file = tempfile.NamedTemporaryFile(
                            mode="w",
                            encoding="utf-8",
                            buffering=1,
                            delete=False,
                            prefix=f"worker_{resolved_name}_",
                            suffix=".log"
                        )
                        log_file_path = log_file.name
                    
                    # Store reference to stderr file
                    self.worker_stderr_files[resolved_name] = (log_file, log_file_path)
                    
                    cmd = ["calibre-debug", worker_path, lib_path]
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=log_file,
                        text=True,
                        bufsize=1,
                        encoding='utf-8'
                    )
                    self.workers[resolved_name] = proc
                    self.worker_stats[resolved_name] = {'last_used': time.time(), 'active_requests': 0}
                except FileNotFoundError:
                    logging.error("get_worker returning error 'calibre-debug not found in PATH.'")
                    raise RuntimeError("calibre-debug executable not found.")
            
            # Increment tracking logic:
            if resolved_name in self.worker_stats:
                self.worker_stats[resolved_name]['active_requests'] += 1
                self.worker_stats[resolved_name]['last_used'] = time.time()
                
            logging.debug(f"get_worker returning result '{resolved_name}'")
            return proc, resolved_name

    def _extract_stderr_error(self, library_name):
        """
        Extract the most relevant error message from the worker's stderr file.
        Returns a string with the error message, or None if no error found.
        """
        if library_name not in self.worker_stderr_files:
            return None
        
        _, stderr_path = self.worker_stderr_files[library_name]
        
        try:
            # Read the last 50 lines of stderr (to avoid reading huge files)
            with open(stderr_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                last_lines = lines[-50:] if len(lines) > 50 else lines
            
            # Look for JSON error messages (most recent first)
            json_errors = []
            for line in reversed(last_lines):
                line = line.strip()
                if not line:
                    continue
                
                # Skip Python warnings and other noise
                if any(keyword in line for keyword in ['Warning:', 'SyntaxWarning:', 'DeprecationWarning:', 
                                                        'FutureWarning:', '--- Worker Started at']):
                    continue
                
                # Try to parse as JSON
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and 'error' in data:
                        return data['error']
                except json.JSONDecodeError:
                    continue
            
            # If no JSON errors found, return the last non-empty, non-warning line
            for line in reversed(last_lines):
                line = line.strip()
                if line and not any(keyword in line for keyword in ['Warning:', 'SyntaxWarning:', 
                                                                      'DeprecationWarning:', 'FutureWarning:',
                                                                      '--- Worker Started at']):
                    return line
            
            return None
            
        except Exception as e:
            # If we can't read the stderr file, just return None
            return None

    def send_rpc(self, library_name, method, params=None):
        if params is None:
            params = {}
            
        proc, resolved_name = self.get_worker(library_name)
        
        with self.lock:
            req_id = self.request_id_counter
            self.request_id_counter += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id
        }
        
        try:
            json_str = json.dumps(request)
            proc.stdin.write(json_str + "\n")
            proc.stdin.flush()
            
            while True:
                response_line = proc.stdout.readline()
                if not response_line:
                    # Worker process terminated unexpectedly
                    # Extract error message from stderr if available
                    stderr_error = self._extract_stderr_error(resolved_name)
                    
                    with self.lock:
                        if resolved_name in self.workers:
                            del self.workers[resolved_name]
                    
                    if stderr_error:
                        logging.error(f"Worker process terminated unexpectedly: {stderr_error}")
                        raise RuntimeError(f"Worker process terminated unexpectedly: {stderr_error}")
                    else:
                        logging.error("Worker process terminated unexpectedly")
                        raise RuntimeError("Worker process terminated unexpectedly")
                
                stripped = response_line.strip()
                if not stripped:
                    continue
                    
                try:
                    response = json.loads(stripped)
                    if "jsonrpc" in response:
                        break
                    else:
                        logging.debug(f"Worker emitted non-RPC JSON: {stripped}")
                except json.JSONDecodeError:
                    logging.debug(f"Worker emitted non-RPC JSON: {stripped}")
                    continue
            
            if "error" in response:
                logging.error(f"Worker Error: {response['error'].get('message', 'Unknown error')}")
                raise RuntimeError(f"Worker Error: {response['error'].get('message', 'Unknown error')}")
                
            return response.get("result")
            
        except BrokenPipeError:
            with self.lock:
                if resolved_name in self.workers:
                    del self.workers[resolved_name]
                if resolved_name in self.worker_stats:
                    del self.worker_stats[resolved_name]
            logging.error(f"Communication with Calibre worker for '{library_name}' failed.")
            raise RuntimeError(f"Communication with Calibre worker for '{library_name}' failed.")
        finally:
            with self.lock:
                if resolved_name in self.worker_stats:
                    self.worker_stats[resolved_name]['active_requests'] -= 1
                    self.worker_stats[resolved_name]['last_used'] = time.time()

    def _cleanup_workers(self):
        """Background thread that monitors and shuts down idle workers."""
        while not self._shutdown_event.wait(5.0): # Run check every 5 seconds
            with self.lock:
                for lib_name in list(self.workers.keys()):
                    proc = self.workers[lib_name]
                    stats = self.worker_stats.get(lib_name)
                    if not stats:
                        continue
                        
                    active = stats['active_requests']
                    last_used = stats['last_used']
                    
                    if active > 0:
                        continue
                        
                    # Determine timeout threshold
                    lib_conf = self.config_manager.get_library_config(lib_name)
                    if lib_conf:
                        timeout = lib_conf.get("worker_timeout")
                        if timeout is None:
                            timeout = self.config_manager.get_global_setting("worker_timeout")
                    else:
                        timeout = self.config_manager.get_global_setting("worker_timeout")
                        
                    # Default: never expire if timeout is missing, 0, or null
                    if not timeout or timeout <= 0:
                        continue
                        
                    time_idle = time.time() - last_used
                    if time_idle > timeout:
                        logging.debug(f"Worker for '{lib_name}' has been idle for {time_idle:.1f}s (timeout: {timeout}s), shutting it down.")
                        if proc.poll() is None:
                            proc.terminate()
                        del self.workers[lib_name]
                        del self.worker_stats[lib_name]
                        # Assume shutdown cleanup routine will handle stderr log cleanup when worker restarts or completely shuts down.

    def shutdown(self):
        """Terminates all worker processes and cleans up stderr files."""
        self._shutdown_event.set()
        with self.lock:
            for lib_name, proc in self.workers.items():
                if proc.poll() is None:
                    proc.terminate()
            
            for _ in range(10):
                if all(p.poll() is not None for p in self.workers.values()):
                    break
                time.sleep(0.1)
                
            for proc in self.workers.values():
                if proc.poll() is None:
                    proc.kill()
            
            # Clean up stderr files
            for lib_name, (file_handle, file_path) in list(self.worker_stderr_files.items()):
                try:
                    file_handle.close()
                except:
                    pass
                
                # Delete temporary files
                if file_path.startswith(tempfile.gettempdir()):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
            self.workers.clear()
            self.worker_stderr_files.clear()
            self.worker_stats.clear()
