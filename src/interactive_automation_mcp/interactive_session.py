import pexpect
import signal
import os
from typing import List, Optional, Dict, Any, Union, Tuple

class InteractiveSession:
    """Represents a single interactive terminal session"""
    
    def __init__(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
        environment: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ):
        self.session_id = session_id
        self.command = command
        self.timeout = timeout
        self.environment = environment or {}
        self.working_directory = working_directory
        
        self.process: Optional[pexpect.spawn] = None
        self.output_buffer: List[str] = []
        self.automation_patterns: List[Dict[str, Any]] = []
        self.is_active = False
        self.exit_code: Optional[int] = None
        
        # State tracking
        self.current_prompt = None
        self.last_command = None
        self.command_history: List[str] = []
    
    async def initialize(self):
        """Initialize the interactive session"""
        try:
            # Set up environment
            env = os.environ.copy()
            env.update(self.environment)
            
            # Spawn the process
            self.process = pexpect.spawn(
                self.command,
                timeout=self.timeout,
                env=env,
                cwd=self.working_directory,
                encoding='utf-8',
                codec_errors='replace'
            )
            
            # Set up logging
            if hasattr(self.process, 'logfile_read'):
                self.process.logfile_read = open(f'/tmp/session_{self.session_id}.log', 'w')
            
            self.is_active = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize session: {str(e)}")
    
    async def expect_and_respond(
        self,
        pattern: Union[str, List[str]],
        response: str,
        timeout: Optional[int] = None,
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Wait for pattern and send response"""
        
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        try:
            # Prepare patterns
            if isinstance(pattern, str):
                patterns = [pattern]
            else:
                patterns = pattern
            
            # Add EOF and TIMEOUT to patterns
            patterns.extend([pexpect.EOF, pexpect.TIMEOUT])
            
            # Set timeout
            original_timeout = self.process.timeout
            if timeout:
                self.process.timeout = timeout
            
            # Wait for pattern
            index = self.process.expect(patterns)
            
            # Restore timeout
            self.process.timeout = original_timeout
            
            # Process result
            if index < len(patterns) - 2:  # Pattern matched
                matched_pattern = patterns[index]
                before_text = self.process.before or ""
                after_text = self.process.after or ""
                
                # Store output
                self.output_buffer.append(before_text)
                
                # Send response
                if response:
                    self.process.sendline(response)
                    self.command_history.append(response)
                    self.last_command = response
                
                return {
                    "success": True,
                    "matched_pattern": matched_pattern,
                    "matched_index": index,
                    "before": before_text,
                    "after": after_text,
                    "response_sent": response
                }
            
            elif index == len(patterns) - 2:  # EOF
                self.is_active = False
                self.exit_code = self.process.exitstatus
                return {
                    "success": False,
                    "reason": "process_ended",
                    "exit_code": self.exit_code,
                    "before": self.process.before or ""
                }
            
            else:  # TIMEOUT
                return {
                    "success": False,
                    "reason": "timeout",
                    "before": self.process.before or ""
                }
                
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e)
            }
    
    async def send_input(self, input_text: str, add_newline: bool = True):
        """Send input to the session"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        if add_newline:
            self.process.sendline(input_text)
        else:
            self.process.send(input_text)
        
        self.command_history.append(input_text)
        self.last_command = input_text
    
    async def send_signal(self, sig: int):
        """Send signal to the process"""
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")
        
        self.process.kill(sig)
    
    async def get_output(self, lines: Optional[int] = None) -> str:
        """Get output from the session buffer"""
        if lines is None:
            return "\n".join(self.output_buffer)
        else:
            return "\n".join(self.output_buffer[-lines:])
    
    async def clear_output_buffer(self):
        """Clear the output buffer"""
        self.output_buffer.clear()
    
    async def terminate(self):
        """Terminate the session"""
        if self.process and self.is_active:
            try:
                # Try graceful termination first
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                # Force kill if needed
                self.process.kill(signal.SIGKILL)
            finally:
                self.is_active = False
                if hasattr(self.process, 'logfile_read') and self.process.logfile_read:
                    self.process.logfile_read.close()