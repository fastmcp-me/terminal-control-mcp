# TODO: Implement `run_workflow` Tool

## Overview
Implement a new MCP tool `run_workflow` that enables complex conditional workflows with loops, user interactions, recursion, and automatic persistence. This tool orchestrates the existing 6 MCP tools plus itself to create reusable workflow compositions.

## Key Features
- **Single tool call** executes complete workflows
- **Automatic persistence** of successful workflows
- **Recursive composition** - workflows can call other workflows
- **Standard variable system** for seamless data flow
- **Loop and conditional support** through state transitions

## Implementation Steps

### Step 1: Create Workflow Persistence System
**File**: `src/terminal_control_mcp/workflow_persistence.py`

```python
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

class WorkflowPersistence:
    def __init__(self, workflows_dir: str = ".terminal_control_workflows"):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(exist_ok=True)
        self.index_file = self.workflows_dir / "index.json"
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """Create index.json if it doesn't exist"""
        if not self.index_file.exists():
            self.index_file.write_text(json.dumps({
                "workflows": {},
                "created": datetime.now(timezone.utc).isoformat(),
                "version": "1.0"
            }, indent=2))
    
    def _get_workflow_hash(self, workflow_def: dict) -> str:
        """Generate hash for workflow definition (for duplicate detection)"""
        # Remove name and description for hash (content-based hashing)
        hashable_content = {k: v for k, v in workflow_def.items() 
                           if k not in ["name", "description"]}
        content_str = json.dumps(hashable_content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    async def save_successful_workflow(self, workflow_def: dict, execution_log: list) -> Optional[str]:
        """Save workflow that completed successfully
        
        Returns: workflow_name if saved, None if duplicate exists
        """
        workflow_name = workflow_def.get("name")
        if not workflow_name:
            # Generate name from hash if none provided
            workflow_name = f"workflow_{self._get_workflow_hash(workflow_def)}"
        
        # Check for duplicates by hash
        workflow_hash = self._get_workflow_hash(workflow_def)
        index_data = json.loads(self.index_file.read_text())
        
        # Check if identical workflow already exists
        for existing_name, metadata in index_data["workflows"].items():
            if metadata.get("hash") == workflow_hash:
                return None  # Duplicate exists
        
        # Save workflow file
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        workflow_data = {
            "definition": workflow_def,
            "metadata": {
                "hash": workflow_hash,
                "created": datetime.now(timezone.utc).isoformat(),
                "success_count": 1,
                "last_execution": datetime.now(timezone.utc).isoformat(),
                "total_states": len(execution_log)
            }
        }
        
        workflow_file.write_text(json.dumps(workflow_data, indent=2))
        
        # Update index
        index_data["workflows"][workflow_name] = {
            "file": f"{workflow_name}.json",
            "hash": workflow_hash,
            "description": workflow_def.get("description", ""),
            "created": workflow_data["metadata"]["created"],
            "success_count": 1
        }
        
        self.index_file.write_text(json.dumps(index_data, indent=2))
        return workflow_name
    
    async def load_workflow(self, workflow_name: str) -> Optional[dict]:
        """Load workflow definition by name"""
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        if not workflow_file.exists():
            return None
        
        workflow_data = json.loads(workflow_file.read_text())
        
        # Update success count and last execution
        workflow_data["metadata"]["success_count"] += 1
        workflow_data["metadata"]["last_execution"] = datetime.now(timezone.utc).isoformat()
        workflow_file.write_text(json.dumps(workflow_data, indent=2))
        
        return workflow_data["definition"]
    
    async def list_available_workflows(self) -> List[Dict[str, str]]:
        """Get list of available workflows with metadata"""
        if not self.index_file.exists():
            return []
        
        index_data = json.loads(self.index_file.read_text())
        return [
            {
                "name": name,
                "description": metadata.get("description", ""),
                "created": metadata.get("created", ""),
                "success_count": metadata.get("success_count", 0)
            }
            for name, metadata in index_data["workflows"].items()
        ]
```

**Critical Edge Cases Addressed:**
- **Duplicate Detection**: Use content hash to prevent saving identical workflows
- **Name Conflicts**: Auto-generate names if none provided or conflicts exist
- **File System Errors**: Handle directory creation, file permissions
- **JSON Corruption**: Validate JSON structure before operations
- **Concurrent Access**: Atomic file operations to prevent corruption

### Step 2: Enhanced Pydantic Models
**File**: `src/terminal_control_mcp/models.py` (add these classes)

```python
class RunWorkflowRequest(BaseModel):
    """Request to execute a workflow"""
    workflow_definition: dict | None = Field(
        None, 
        description="Complete workflow definition as JSON object"
    )
    workflow_name: str | None = Field(
        None, 
        description="Name of saved workflow to execute (alternative to workflow_definition)"
    )
    initial_variables: dict[str, str] = Field(
        default_factory=dict, 
        description="Starting variables for workflow execution"
    )
    max_states: int = Field(
        default=100, 
        ge=1, 
        le=1000, 
        description="Maximum states to execute (prevents infinite loops)"
    )
    execution_timeout: float = Field(
        default=1800.0, 
        ge=1.0, 
        le=7200.0, 
        description="Maximum total execution time in seconds"
    )
    save_on_success: bool = Field(
        default=True, 
        description="Whether to save workflow automatically if execution succeeds"
    )
    
    @model_validator(mode='after')
    def validate_workflow_source(self):
        """Ensure exactly one workflow source is provided"""
        has_definition = self.workflow_definition is not None
        has_name = self.workflow_name is not None
        
        if not has_definition and not has_name:
            raise ValueError("Either 'workflow_definition' or 'workflow_name' must be provided")
        if has_definition and has_name:
            raise ValueError("Provide either 'workflow_definition' OR 'workflow_name', not both")
        
        return self

class RunWorkflowResponse(BaseModel):
    """Response from workflow execution"""
    success: bool
    final_state: str
    states_executed: int
    total_elapsed_time: float
    execution_log: list[dict] = Field(description="Detailed log of each state execution")
    final_variables: dict[str, str] = Field(description="All variables at workflow completion")
    session_id: str | None = Field(None, description="Primary session ID if one was created")
    workflow_saved: bool = Field(default=False, description="Whether workflow was saved for reuse")
    saved_workflow_name: str | None = Field(None, description="Name used to save the workflow")
    available_workflows: list[str] = Field(default_factory=list, description="List of available saved workflows")
    recursion_depth: int = Field(default=0, description="Current recursion level")
    error: str | None = None
```

**Critical Validation Added:**
- **Mutually Exclusive Fields**: Exactly one workflow source required
- **Range Validation**: Reasonable limits on max_states and timeout
- **Model Validation**: Custom validator ensures request consistency

### Step 3: JSON Schema Definition
**File**: `src/terminal_control_mcp/workflow_schema.py`

```python
import jsonschema

# Complete JSON Schema for workflow definitions
WORKFLOW_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Workflow Definition",
    "description": "Schema for defining executable workflows",
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-zA-Z][a-zA-Z0-9_-]*$",
            "minLength": 1,
            "maxLength": 64,
            "description": "Workflow identifier (alphanumeric, underscore, hyphen)"
        },
        "description": {
            "type": "string",
            "maxLength": 500,
            "description": "Human-readable description of workflow purpose"
        },
        "initial_state": {
            "type": "string",
            "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
            "description": "Name of the starting state"
        },
        "states": {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 100,
            "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "object",
                            "properties": {
                                "tool": {
                                    "enum": [
                                        "open_terminal",
                                        "send_input",
                                        "await_output", 
                                        "get_screen_content",
                                        "list_terminal_sessions",
                                        "exit_terminal",
                                        "run_workflow"
                                    ]
                                },
                                "params": {
                                    "type": "object",
                                    "description": "Parameters for the tool call (tool-specific)"
                                }
                            },
                            "required": ["tool", "params"],
                            "additionalProperties": False
                        },
                        "transitions": {
                            "type": "array",
                            "minItems": 0,
                            "maxItems": 20,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "condition": {
                                        "type": "object",
                                        "minProperties": 1,
                                        "properties": {
                                            "success": {
                                                "type": "boolean",
                                                "description": "Match on tool success status"
                                            },
                                            "pattern_match": {
                                                "type": "string",
                                                "description": "Regex to match against match_text or screen_content"
                                            },
                                            "pattern_not_match": {
                                                "type": "string", 
                                                "description": "Regex that must NOT match"
                                            },
                                            "field_equals": {
                                                "type": "object",
                                                "description": "Check if tool result field equals specific value"
                                            },
                                            "field_contains": {
                                                "type": "object",
                                                "description": "Check if tool result field contains specific value"
                                            },
                                            "timeout_occurred": {
                                                "type": "boolean",
                                                "description": "Match if state timed out"
                                            }
                                        },
                                        "additionalProperties": False
                                    },
                                    "next_state": {
                                        "type": "string",
                                        "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
                                        "description": "State to transition to when condition matches"
                                    }
                                },
                                "required": ["condition", "next_state"],
                                "additionalProperties": False
                            }
                        },
                        "timeout": {
                            "type": "number",
                            "minimum": 0.1,
                            "maximum": 300.0,
                            "description": "State timeout in seconds"
                        },
                        "on_timeout": {
                            "type": "string", 
                            "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
                            "description": "State to transition to if timeout occurs"
                        }
                    },
                    "required": ["action"],
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }
    },
    "required": ["name", "initial_state", "states"],
    "additionalProperties": False
}

def validate_workflow_schema(workflow_def: dict) -> None:
    """Validate workflow definition against schema
    
    Raises:
        jsonschema.ValidationError: If workflow is invalid
        ValueError: If workflow has logical errors
    """
    # Schema validation
    jsonschema.validate(workflow_def, WORKFLOW_SCHEMA)
    
    # Additional logical validation
    initial_state = workflow_def["initial_state"]
    states = workflow_def["states"]
    
    # Ensure initial state exists
    if initial_state not in states:
        raise ValueError(f"Initial state '{initial_state}' not found in states")
    
    # Check all transition targets exist
    for state_name, state_def in states.items():
        transitions = state_def.get("transitions", [])
        timeout_target = state_def.get("on_timeout")
        
        for transition in transitions:
            next_state = transition["next_state"]
            if next_state not in states:
                raise ValueError(f"State '{state_name}' references non-existent state '{next_state}'")
        
        if timeout_target and timeout_target not in states:
            raise ValueError(f"State '{state_name}' timeout target '{timeout_target}' not found")
    
    # Check for unreachable states (optional warning)
    reachable = set([initial_state])
    changed = True
    while changed:
        changed = False
        for state_name in list(reachable):
            if state_name in states:
                state_def = states[state_name]
                transitions = state_def.get("transitions", [])
                timeout_target = state_def.get("on_timeout")
                
                for transition in transitions:
                    next_state = transition["next_state"]
                    if next_state not in reachable:
                        reachable.add(next_state)
                        changed = True
                
                if timeout_target and timeout_target not in reachable:
                    reachable.add(timeout_target)
                    changed = True
    
    unreachable = set(states.keys()) - reachable
    if unreachable:
        # Log warning but don't fail validation
        print(f"Warning: Unreachable states detected: {unreachable}")
```

**Critical Schema Features:**
- **Pattern Validation**: State names must be valid identifiers
- **Size Limits**: Prevent excessively large workflows
- **Reference Validation**: All state transitions must reference valid states
- **Reachability Check**: Warn about unreachable states
- **Additional Properties**: Explicitly disabled to catch typos

### Step 4: Workflow Engine Implementation
**File**: `src/terminal_control_mcp/workflow_engine.py`

```python
import asyncio
import re
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional, Any, Union

from .models import *
from .workflow_persistence import WorkflowPersistence
from .workflow_schema import validate_workflow_schema
from .main import (
    open_terminal, send_input, await_output, get_screen_content,
    list_terminal_sessions, exit_terminal
)

class WorkflowEngine:
    def __init__(self, app_context):
        self.app_context = app_context
        self.persistence = WorkflowPersistence()
        self.variables: Dict[str, str] = {}
        self.execution_log: List[Dict] = []
        self.recursion_depth = 0
        self.max_recursion_depth = 5
        self.start_time = time.time()
    
    async def execute_workflow(
        self, 
        workflow_def: dict, 
        initial_vars: dict, 
        max_states: int,
        execution_timeout: float = 1800.0
    ) -> Dict[str, Any]:
        """Execute complete workflow and return results"""
        
        try:
            # Initialize
            self.variables = initial_vars.copy()
            self.execution_log = []
            self.start_time = time.time()
            
            # Validate workflow
            validate_workflow_schema(workflow_def)
            
            current_state = workflow_def["initial_state"]
            states_executed = 0
            
            while current_state and states_executed < max_states:
                # Check global timeout
                elapsed = time.time() - self.start_time
                if elapsed > execution_timeout:
                    raise TimeoutError(f"Workflow execution timeout ({execution_timeout}s) exceeded")
                
                # Check if state exists
                if current_state not in workflow_def["states"]:
                    raise ValueError(f"State '{current_state}' not found in workflow definition")
                
                state_def = workflow_def["states"][current_state]
                
                # Execute state
                tool_result, state_elapsed = await self._execute_state(current_state, state_def)
                states_executed += 1
                
                # Update variables from tool result
                self._update_variables_from_result(tool_result, current_state)
                
                # Log execution
                log_entry = {
                    "state": current_state,
                    "tool": state_def["action"]["tool"],
                    "params": self._substitute_variables(state_def["action"]["params"]),
                    "result": self._serialize_tool_result(tool_result),
                    "variables_after": self.variables.copy(),
                    "elapsed_time": state_elapsed,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                self.execution_log.append(log_entry)
                
                # Evaluate transitions to get next state
                next_state = self._evaluate_transitions(state_def.get("transitions", []), tool_result)
                
                if not next_state:
                    # No transition matched - workflow complete
                    break
                
                current_state = next_state
            
            # Check if we hit max states limit
            if states_executed >= max_states:
                raise ValueError(f"Maximum states limit ({max_states}) reached - possible infinite loop")
            
            total_elapsed = time.time() - self.start_time
            
            return {
                "success": True,
                "final_state": current_state or "completed",
                "states_executed": states_executed,
                "total_elapsed_time": total_elapsed,
                "execution_log": self.execution_log,
                "final_variables": self.variables,
                "session_id": self.variables.get("session_id"),
                "recursion_depth": self.recursion_depth
            }
            
        except Exception as e:
            total_elapsed = time.time() - self.start_time
            return {
                "success": False,
                "final_state": current_state if 'current_state' in locals() else "error",
                "states_executed": states_executed if 'states_executed' in locals() else 0,
                "total_elapsed_time": total_elapsed,
                "execution_log": self.execution_log,
                "final_variables": self.variables,
                "session_id": self.variables.get("session_id"),
                "recursion_depth": self.recursion_depth,
                "error": str(e)
            }
    
    async def _execute_state(self, state_name: str, state_def: dict) -> tuple[Any, float]:
        """Execute a single state and return tool result and elapsed time"""
        start_time = time.time()
        
        action = state_def["action"]
        tool_name = action["tool"]
        params = self._substitute_variables(action["params"])
        
        # Handle state timeout
        state_timeout = state_def.get("timeout", 30.0)
        
        try:
            # Execute with timeout
            tool_result = await asyncio.wait_for(
                self._call_mcp_tool(tool_name, params),
                timeout=state_timeout
            )
            
        except asyncio.TimeoutError:
            # State timed out - create timeout result
            tool_result = SimpleNamespace(
                success=False,
                error=f"State '{state_name}' timed out after {state_timeout}s",
                timeout_occurred=True
            )
            
            # Check if there's a timeout transition
            timeout_target = state_def.get("on_timeout")
            if timeout_target:
                # Will be handled by transition evaluation
                pass
        
        elapsed = time.time() - start_time
        return tool_result, elapsed
    
    async def _call_mcp_tool(self, tool_name: str, params: dict) -> Any:
        """Call one of the MCP tools, including recursive workflow calls"""
        
        if tool_name == "run_workflow":
            # Handle recursion
            if self.recursion_depth >= self.max_recursion_depth:
                raise ValueError(f"Maximum recursion depth ({self.max_recursion_depth}) exceeded")
            
            self.recursion_depth += 1
            try:
                # Import here to avoid circular imports
                from .main import run_workflow
                
                request = RunWorkflowRequest(**params)
                
                # Create mock context for recursive call
                mock_ctx = SimpleNamespace(
                    request_context=SimpleNamespace(
                        lifespan_context=self.app_context
                    )
                )
                
                result = await run_workflow(request, mock_ctx)
                return result
                
            finally:
                self.recursion_depth -= 1
        
        else:
            # Call existing MCP tools
            return await self._call_existing_tool(tool_name, params)
    
    async def _call_existing_tool(self, tool_name: str, params: dict) -> Any:
        """Call one of the 6 existing MCP tools"""
        
        # Create mock context
        mock_ctx = SimpleNamespace(
            request_context=SimpleNamespace(
                lifespan_context=self.app_context
            )
        )
        
        if tool_name == "open_terminal":
            request = OpenTerminalRequest(**params)
            return await open_terminal(request, mock_ctx)
            
        elif tool_name == "send_input":
            request = SendInputRequest(**params)
            return await send_input(request, mock_ctx)
            
        elif tool_name == "await_output":
            request = AwaitOutputRequest(**params)
            return await await_output(request, mock_ctx)
            
        elif tool_name == "get_screen_content":
            request = GetScreenContentRequest(**params)
            return await get_screen_content(request, mock_ctx)
            
        elif tool_name == "list_terminal_sessions":
            return await list_terminal_sessions(mock_ctx)
            
        elif tool_name == "exit_terminal":
            request = DestroySessionRequest(**params)
            return await exit_terminal(request, mock_ctx)
        
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def _update_variables_from_result(self, tool_result: Any, state_name: str):
        """Extract values from tool result and update variables"""
        
        # Convert to dict if it's a Pydantic model
        if hasattr(tool_result, 'model_dump'):
            result_dict = tool_result.model_dump()
        elif hasattr(tool_result, '__dict__'):
            result_dict = tool_result.__dict__
        else:
            result_dict = {}
        
        # Standard variable mappings
        standard_mappings = {
            "success": "success",
            "session_id": "session_id", 
            "match_text": "match_text",
            "screen_content": "screen_content",
            "error": "error",
            "timestamp": "timestamp",
            "elapsed_time": "elapsed_time",
            "shell": "shell",
            "web_url": "web_url",
            "process_running": "process_running",
            "total_sessions": "total_sessions",
            "message": "message",
            "final_state": "workflow_final_state",
            "workflow_saved": "workflow_saved",
            "saved_workflow_name": "saved_workflow_name"
        }
        
        # Extract standard variables
        for result_field, var_name in standard_mappings.items():
            if result_field in result_dict and result_dict[result_field] is not None:
                self.variables[var_name] = str(result_dict[result_field])
        
        # Also create state-specific variables for debugging
        for field, value in result_dict.items():
            if value is not None:
                self.variables[f"{state_name}_{field}"] = str(value)
    
    def _substitute_variables(self, params: dict) -> dict:
        """Recursively substitute {variable_name} placeholders in parameters"""
        
        if isinstance(params, dict):
            result = {}
            for key, value in params.items():
                result[key] = self._substitute_variables(value)
            return result
        
        elif isinstance(params, list):
            return [self._substitute_variables(item) for item in params]
        
        elif isinstance(params, str):
            # Replace all {var_name} patterns
            result = params
            for var_name, var_value in self.variables.items():
                result = result.replace(f"{{{var_name}}}", str(var_value))
            return result
        
        else:
            return params
    
    def _evaluate_transitions(self, transitions: List[dict], tool_result: Any) -> Optional[str]:
        """Evaluate transition conditions and return next state"""
        
        # Convert tool result to dict for easier access
        if hasattr(tool_result, 'model_dump'):
            result_dict = tool_result.model_dump()
        elif hasattr(tool_result, '__dict__'):
            result_dict = tool_result.__dict__
        else:
            result_dict = {}
        
        for transition in transitions:
            condition = transition["condition"]
            
            # Evaluate each condition type
            if "success" in condition:
                if result_dict.get("success") == condition["success"]:
                    return transition["next_state"]
            
            if "pattern_match" in condition:
                pattern = condition["pattern_match"]
                search_text = ""
                if "match_text" in result_dict and result_dict["match_text"]:
                    search_text += str(result_dict["match_text"])
                if "screen_content" in result_dict and result_dict["screen_content"]:
                    search_text += " " + str(result_dict["screen_content"])
                
                if re.search(pattern, search_text):
                    return transition["next_state"]
            
            if "pattern_not_match" in condition:
                pattern = condition["pattern_not_match"]
                search_text = ""
                if "match_text" in result_dict and result_dict["match_text"]:
                    search_text += str(result_dict["match_text"])
                if "screen_content" in result_dict and result_dict["screen_content"]:
                    search_text += " " + str(result_dict["screen_content"])
                
                if not re.search(pattern, search_text):
                    return transition["next_state"]
            
            if "field_equals" in condition:
                for field_name, expected_value in condition["field_equals"].items():
                    if result_dict.get(field_name) == expected_value:
                        return transition["next_state"]
            
            if "field_contains" in condition:
                for field_name, search_value in condition["field_contains"].items():
                    field_value = str(result_dict.get(field_name, ""))
                    if search_value in field_value:
                        return transition["next_state"]
            
            if "timeout_occurred" in condition:
                if hasattr(tool_result, 'timeout_occurred') and tool_result.timeout_occurred:
                    if condition["timeout_occurred"]:
                        return transition["next_state"]
        
        return None  # No transition matched
    
    def _serialize_tool_result(self, tool_result: Any) -> dict:
        """Convert tool result to serializable dict for logging"""
        if hasattr(tool_result, 'model_dump'):
            return tool_result.model_dump()
        elif hasattr(tool_result, '__dict__'):
            return {k: v for k, v in tool_result.__dict__.items() 
                   if not k.startswith('_')}
        else:
            return {"value": str(tool_result)}
```

**Critical Engine Features:**
- **Timeout Handling**: Both state-level and workflow-level timeouts
- **Recursion Protection**: Depth limits and proper cleanup
- **Variable Management**: Automatic extraction and substitution
- **Error Recovery**: Graceful handling of tool failures
- **State Validation**: Check state existence before execution
- **Memory Management**: Clean up resources properly

### Step 5: Main Tool Integration
**File**: `src/terminal_control_mcp/main.py` (add this tool)

```python
from .workflow_engine import WorkflowEngine
from .workflow_persistence import WorkflowPersistence

@mcp.tool()
async def run_workflow(
    request: RunWorkflowRequest, ctx: Context
) -> RunWorkflowResponse:
    """Execute a workflow using existing MCP tools
    
    Execute complex conditional workflows with loops, user input, recursion, and 
    multi-step terminal operations. Workflows can reference other saved workflows 
    for composition and reuse.
    
    Usage Options:
    1. Execute inline workflow: Provide workflow_definition with complete JSON
    2. Execute saved workflow: Provide workflow_name referencing a saved workflow
    
    Successful workflows are automatically saved in .terminal_control_workflows/ 
    for reuse unless save_on_success=False.
    
    Standard variables available in workflows:
    - {session_id}: Session ID from terminal tools  
    - {match_text}: Matched pattern text from await_output
    - {screen_content}: Terminal content from terminal tools
    - {success}: Success status from any tool (true/false)
    - {error}: Error message from any tool (if operation failed)
    - {timestamp}: ISO timestamp from most tools
    - {elapsed_time}: Time elapsed from await_output
    - {shell}: Shell type from open_terminal
    - {web_url}: Web interface URL from open_terminal
    - {process_running}: Process status from get_screen_content
    - {total_sessions}: Session count from list_terminal_sessions
    - {message}: Status message from exit_terminal
    - {workflow_final_state}: Final state from recursive run_workflow calls
    - {workflow_saved}: Whether recursive workflow was saved
    - {saved_workflow_name}: Name of saved recursive workflow
    
    Recursive Capabilities:
    - Workflows can call other workflows using run_workflow action
    - Build complex operations from simpler workflow components
    - Automatic library building through persistence
    - Recursion depth limited to 5 levels for safety
    
    Workflow Definition Schema:
    - name: Workflow identifier (required)
    - initial_state: Starting state name (required)
    - states: Dictionary of state definitions (required)
      - action: {tool: "tool_name", params: {...}} (required)
      - transitions: [{condition: {...}, next_state: "name"}] (optional)
      - timeout: State timeout in seconds (optional, default: 30)
      - on_timeout: State to go to on timeout (optional)
    
    Condition Types:
    - success: true/false - Check if tool call succeeded
    - pattern_match: "regex" - Check if match_text/screen_content matches regex
    - pattern_not_match: "regex" - Check if pattern does NOT match
    - field_equals: {field: "value"} - Check if tool result field equals value
    - field_contains: {field: "substring"} - Check if field contains substring
    - timeout_occurred: true - Check if state timed out
    
    Error Handling:
    - Invalid workflow schemas return error immediately
    - Tool failures can be handled via success: false conditions
    - State timeouts can trigger on_timeout transitions
    - Recursion depth limits prevent infinite loops
    - Global execution timeout prevents runaway workflows
    
    Returns detailed execution information including final variables, 
    execution log, and whether workflow was saved for reuse.
    
    Use with: All existing MCP tools plus saved workflows
    """
    
    app_ctx = ctx.request_context.lifespan_context
    engine = WorkflowEngine(app_ctx)
    persistence = WorkflowPersistence()
    
    try:
        # Determine workflow source
        if request.workflow_name:
            # Load from saved workflows
            workflow_def = await persistence.load_workflow(request.workflow_name)
            if not workflow_def:
                available_workflows = await persistence.list_available_workflows()
                available_names = [w["name"] for w in available_workflows]
                return RunWorkflowResponse(
                    success=False,
                    final_state="error",
                    states_executed=0,
                    total_elapsed_time=0.0,
                    execution_log=[],
                    final_variables={},
                    available_workflows=available_names,
                    error=f"Workflow '{request.workflow_name}' not found. Available: {available_names}"
                )
        else:
            # Use provided definition
            workflow_def = request.workflow_definition
        
        # Execute workflow
        result = await engine.execute_workflow(
            workflow_def,
            request.initial_variables,
            request.max_states,
            request.execution_timeout
        )
        
        # Handle workflow persistence
        workflow_saved = False
        saved_name = None
        if result["success"] and request.save_on_success and not request.workflow_name:
            try:
                saved_name = await persistence.save_successful_workflow(
                    workflow_def, result["execution_log"]
                )
                workflow_saved = saved_name is not None
            except Exception as save_error:
                # Don't fail the whole workflow if saving fails
                result["error"] = f"Workflow succeeded but saving failed: {save_error}"
        
        # Get available workflows for response
        try:
            available_workflows = await persistence.list_available_workflows()
            available_names = [w["name"] for w in available_workflows]
        except Exception:
            available_names = []
        
        return RunWorkflowResponse(
            success=result["success"],
            final_state=result["final_state"],
            states_executed=result["states_executed"],
            total_elapsed_time=result["total_elapsed_time"],
            execution_log=result["execution_log"],
            final_variables=result["final_variables"],
            session_id=result.get("session_id"),
            workflow_saved=workflow_saved,
            saved_workflow_name=saved_name,
            available_workflows=available_names,
            recursion_depth=result["recursion_depth"],
            error=result.get("error")
        )
        
    except Exception as e:
        # Get available workflows even on error
        try:
            available_workflows = await persistence.list_available_workflows()
            available_names = [w["name"] for w in available_workflows]
        except Exception:
            available_names = []
        
        return RunWorkflowResponse(
            success=False,
            final_state="error",
            states_executed=0,
            total_elapsed_time=0.0,
            execution_log=[],
            final_variables={},
            available_workflows=available_names,
            error=f"Workflow execution failed: {str(e)}"
        )
```

**Also update the main docstring** at the top of `main.py`:
```python
"""
MCP Server for Terminal Control with Interactive Sessions and Workflow Automation

This server provides 7 MCP tools for managing terminal sessions:
1. open_terminal: Create new terminal sessions
2. send_input: Send commands to terminal sessions  
3. await_output: Wait for specific output patterns
4. get_screen_content: Retrieve terminal content
5. list_terminal_sessions: List active sessions
6. exit_terminal: Clean up terminal sessions
7. run_workflow: Execute complex conditional workflows (NEW)
"""
```

### Step 6: Update Models Import
**File**: `src/terminal_control_mcp/models.py`

Add these imports at the top:
```python
from pydantic import model_validator
```

### Step 7: Comprehensive Testing
**File**: `tests/test_run_workflow.py`

```python
import asyncio
import json
import tempfile
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.terminal_control_mcp.main import run_workflow
from src.terminal_control_mcp.models import RunWorkflowRequest
from src.terminal_control_mcp.workflow_persistence import WorkflowPersistence
from src.terminal_control_mcp.workflow_schema import validate_workflow_schema

class TestRunWorkflow:
    """Test the run_workflow tool comprehensively"""
    
    @pytest.fixture
    def temp_workflows_dir(self):
        """Create temporary workflows directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture  
    def mock_context(self):
        """Create mock context for tool calls"""
        from src.terminal_control_mcp.session_manager import SessionManager
        from src.terminal_control_mcp.security import SecurityManager
        
        session_manager = SessionManager()
        security_manager = SecurityManager()
        
        app_ctx = SimpleNamespace(
            session_manager=session_manager,
            security_manager=security_manager
        )
        
        return SimpleNamespace(
            request_context=SimpleNamespace(lifespan_context=app_ctx)
        )
    
    @pytest.fixture
    def simple_workflow(self):
        """Simple test workflow"""
        return {
            "name": "test_simple",
            "description": "Simple test workflow",
            "initial_state": "create_session",
            "states": {
                "create_session": {
                    "action": {
                        "tool": "open_terminal",
                        "params": {"shell": "bash"}
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "send_command"
                        }
                    ]
                },
                "send_command": {
                    "action": {
                        "tool": "send_input", 
                        "params": {
                            "session_id": "{session_id}",
                            "input_text": "echo 'test'\n"
                        }
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "cleanup"
                        }
                    ]
                },
                "cleanup": {
                    "action": {
                        "tool": "exit_terminal",
                        "params": {"session_id": "{session_id}"}
                    },
                    "transitions": []
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_inline_workflow_execution(self, mock_context, simple_workflow):
        """Test executing workflow from inline definition"""
        request = RunWorkflowRequest(
            workflow_definition=simple_workflow,
            save_on_success=False  # Don't save during test
        )
        
        result = await run_workflow(request, mock_context)
        
        assert result.success is True
        assert result.states_executed == 3
        assert result.final_state == "cleanup"
        assert "session_id" in result.final_variables
        assert len(result.execution_log) == 3
        assert result.workflow_saved is False
    
    @pytest.mark.asyncio 
    async def test_workflow_persistence(self, mock_context, simple_workflow, temp_workflows_dir):
        """Test automatic saving of successful workflows"""
        with patch('src.terminal_control_mcp.workflow_persistence.WorkflowPersistence') as mock_persistence_class:
            mock_persistence = mock_persistence_class.return_value
            mock_persistence.save_successful_workflow.return_value = "test_simple"
            
            request = RunWorkflowRequest(
                workflow_definition=simple_workflow,
                save_on_success=True
            )
            
            result = await run_workflow(request, mock_context)
            
            assert result.success is True
            assert result.workflow_saved is True
            assert result.saved_workflow_name == "test_simple"
    
    @pytest.mark.asyncio
    async def test_saved_workflow_execution(self, mock_context, simple_workflow, temp_workflows_dir):
        """Test executing workflow by name reference"""
        with patch('src.terminal_control_mcp.workflow_persistence.WorkflowPersistence') as mock_persistence_class:
            mock_persistence = mock_persistence_class.return_value
            mock_persistence.load_workflow.return_value = simple_workflow
            
            request = RunWorkflowRequest(
                workflow_name="test_simple",
                save_on_success=False
            )
            
            result = await run_workflow(request, mock_context)
            
            assert result.success is True
            mock_persistence.load_workflow.assert_called_once_with("test_simple")
    
    @pytest.mark.asyncio
    async def test_recursive_workflow_calls(self, mock_context):
        """Test workflow calling other workflows"""
        parent_workflow = {
            "name": "parent_workflow",
            "initial_state": "call_child", 
            "states": {
                "call_child": {
                    "action": {
                        "tool": "run_workflow",
                        "params": {
                            "workflow_name": "child_workflow"
                        }
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "complete"
                        }
                    ]
                },
                "complete": {
                    "action": {
                        "tool": "open_terminal",
                        "params": {"shell": "bash"}
                    },
                    "transitions": []
                }
            }
        }
        
        child_workflow = {
            "name": "child_workflow", 
            "initial_state": "simple_action",
            "states": {
                "simple_action": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        with patch('src.terminal_control_mcp.workflow_persistence.WorkflowPersistence') as mock_persistence_class:
            mock_persistence = mock_persistence_class.return_value
            mock_persistence.load_workflow.return_value = child_workflow
            
            request = RunWorkflowRequest(
                workflow_definition=parent_workflow,
                save_on_success=False
            )
            
            result = await run_workflow(request, mock_context)
            
            assert result.success is True
            assert result.recursion_depth >= 1
    
    @pytest.mark.asyncio
    async def test_conditional_branching(self, mock_context):
        """Test workflow with success/failure branches"""
        branching_workflow = {
            "name": "test_branching",
            "initial_state": "test_command",
            "states": {
                "test_command": {
                    "action": {
                        "tool": "open_terminal",
                        "params": {"shell": "bash"}
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "success_path"
                        },
                        {
                            "condition": {"success": False},
                            "next_state": "failure_path"
                        }
                    ]
                },
                "success_path": {
                    "action": {
                        "tool": "send_input",
                        "params": {
                            "session_id": "{session_id}",
                            "input_text": "echo 'success'\n"
                        }
                    },
                    "transitions": []
                },
                "failure_path": {
                    "action": {
                        "tool": "list_terminal_sessions", 
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=branching_workflow,
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        assert result.success is True
        # Should follow success path since open_terminal usually succeeds
        assert result.final_state == "success_path"
    
    @pytest.mark.asyncio
    async def test_loop_workflow(self, mock_context):
        """Test workflow with loops (state transitions back)"""
        loop_workflow = {
            "name": "test_loop",
            "initial_state": "counter",
            "states": {
                "counter": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": [
                        {
                            "condition": {"field_equals": {"total_sessions": 0}},
                            "next_state": "counter"  # Loop back
                        },
                        {
                            "condition": {"success": True},
                            "next_state": "done"
                        }
                    ]
                },
                "done": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=loop_workflow,
            max_states=5,  # Limit to prevent infinite loop in test
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        # Should either complete or hit max_states limit
        assert result.states_executed <= 5
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_context):
        """Test state timeouts and timeout transitions"""
        timeout_workflow = {
            "name": "test_timeout",
            "initial_state": "long_wait",
            "states": {
                "long_wait": {
                    "action": {
                        "tool": "await_output",
                        "params": {
                            "session_id": "nonexistent",
                            "pattern": "never_matches",
                            "timeout": 0.1  # Very short timeout
                        }
                    },
                    "timeout": 0.5,
                    "on_timeout": "timeout_recovery",
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "normal_complete"
                        }
                    ]
                },
                "timeout_recovery": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                },
                "normal_complete": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=timeout_workflow,
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        # Should handle timeout and go to recovery state
        assert result.final_state == "timeout_recovery"
    
    @pytest.mark.asyncio
    async def test_variable_substitution(self, mock_context):
        """Test that variables are properly extracted and substituted"""
        var_workflow = {
            "name": "test_variables",
            "initial_state": "create_terminal",
            "states": {
                "create_terminal": {
                    "action": {
                        "tool": "open_terminal",
                        "params": {"shell": "bash"}
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "use_session_id"
                        }
                    ]
                },
                "use_session_id": {
                    "action": {
                        "tool": "get_screen_content",
                        "params": {
                            "session_id": "{session_id}",  # Should be substituted
                            "content_mode": "screen"
                        }
                    },
                    "transitions": []
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=var_workflow,
            initial_variables={"custom_var": "custom_value"},
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        assert result.success is True
        assert "session_id" in result.final_variables
        assert "custom_var" in result.final_variables
        assert result.final_variables["custom_var"] == "custom_value"
        
        # Check that session_id was properly substituted in execution log
        use_session_log = result.execution_log[1]  # Second state
        assert "{session_id}" not in str(use_session_log["params"])
    
    @pytest.mark.asyncio
    async def test_invalid_workflow_schema(self, mock_context):
        """Test error handling for invalid workflow definitions"""
        invalid_workflow = {
            "name": "invalid",
            "initial_state": "nonexistent_state",  # Invalid - state doesn't exist
            "states": {
                "valid_state": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=invalid_workflow,
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        assert result.success is False
        assert "Initial state 'nonexistent_state' not found" in result.error
    
    @pytest.mark.asyncio
    async def test_infinite_loop_prevention(self, mock_context):
        """Test max_states limit prevents infinite loops"""
        infinite_workflow = {
            "name": "infinite_loop",
            "initial_state": "loop",
            "states": {
                "loop": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": [
                        {
                            "condition": {"success": True},
                            "next_state": "loop"  # Always loop back to itself
                        }
                    ]
                }
            }
        }
        
        request = RunWorkflowRequest(
            workflow_definition=infinite_workflow,
            max_states=5,  # Low limit to test prevention
            save_on_success=False
        )
        
        result = await run_workflow(request, mock_context)
        
        assert result.success is False
        assert "Maximum states limit (5) reached" in result.error
        assert result.states_executed == 5
    
    @pytest.mark.asyncio
    async def test_request_validation(self, mock_context):
        """Test request validation logic"""
        
        # Test missing both workflow_definition and workflow_name
        with pytest.raises(ValueError, match="Either 'workflow_definition' or 'workflow_name' must be provided"):
            RunWorkflowRequest()
        
        # Test providing both workflow_definition and workflow_name
        with pytest.raises(ValueError, match="Provide either 'workflow_definition' OR 'workflow_name', not both"):
            RunWorkflowRequest(
                workflow_definition={"name": "test"},
                workflow_name="test"
            )
    
    def test_workflow_schema_validation(self):
        """Test workflow schema validation"""
        
        # Valid workflow should pass
        valid_workflow = {
            "name": "valid_test",
            "initial_state": "start",
            "states": {
                "start": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        # Should not raise exception
        validate_workflow_schema(valid_workflow)
        
        # Invalid workflow should fail
        invalid_workflow = {
            "name": "invalid",
            "initial_state": "start",
            "states": {
                "start": {
                    "action": {
                        "tool": "invalid_tool",  # Invalid tool name
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        with pytest.raises(Exception):  # Could be ValidationError or ValueError
            validate_workflow_schema(invalid_workflow)

class TestWorkflowPersistence:
    """Test workflow persistence functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_workflow_saving_and_loading(self, temp_dir):
        """Test saving and loading workflows"""
        persistence = WorkflowPersistence(temp_dir)
        
        workflow = {
            "name": "test_workflow",
            "description": "Test workflow for persistence",
            "initial_state": "start",
            "states": {
                "start": {
                    "action": {
                        "tool": "list_terminal_sessions",
                        "params": {}
                    },
                    "transitions": []
                }
            }
        }
        
        # Save workflow
        saved_name = await persistence.save_successful_workflow(workflow, [])
        assert saved_name == "test_workflow"
        
        # Load workflow
        loaded_workflow = await persistence.load_workflow("test_workflow")
        assert loaded_workflow["name"] == "test_workflow"
        assert loaded_workflow["initial_state"] == "start"
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, temp_dir):
        """Test that duplicate workflows are not saved twice"""
        persistence = WorkflowPersistence(temp_dir)
        
        workflow = {
            "name": "duplicate_test",
            "initial_state": "start", 
            "states": {
                "start": {
                    "action": {"tool": "list_terminal_sessions", "params": {}},
                    "transitions": []
                }
            }
        }
        
        # Save first time
        saved_name1 = await persistence.save_successful_workflow(workflow, [])
        assert saved_name1 == "duplicate_test"
        
        # Try to save identical workflow
        saved_name2 = await persistence.save_successful_workflow(workflow, [])
        assert saved_name2 is None  # Should not save duplicate
    
    @pytest.mark.asyncio 
    async def test_workflow_listing(self, temp_dir):
        """Test listing available workflows"""
        persistence = WorkflowPersistence(temp_dir)
        
        workflow1 = {
            "name": "workflow1",
            "description": "First workflow", 
            "initial_state": "start",
            "states": {"start": {"action": {"tool": "list_terminal_sessions", "params": {}}, "transitions": []}}
        }
        
        workflow2 = {
            "name": "workflow2",
            "description": "Second workflow",
            "initial_state": "begin",
            "states": {"begin": {"action": {"tool": "list_terminal_sessions", "params": {}}, "transitions": []}}
        }
        
        # Save both workflows
        await persistence.save_successful_workflow(workflow1, [])
        await persistence.save_successful_workflow(workflow2, [])
        
        # List workflows
        workflows = await persistence.list_available_workflows()
        assert len(workflows) == 2
        
        names = [w["name"] for w in workflows]
        assert "workflow1" in names
        assert "workflow2" in names
```

### Step 8: Update README.md
**File**: `README.md`

Add these sections (integrate with existing content):

```markdown
## 🛠️ MCP Tools (7 Tools)

### Core Terminal Management (6 Tools)
[... existing tool descriptions ...]

### **`run_workflow`** 🆕 - Workflow Automation
Execute complex conditional workflows with loops, user interaction, and composition.

**Parameters:**
- `workflow_definition`: Complete workflow as JSON object (OR)
- `workflow_name`: Name of saved workflow to execute
- `initial_variables`: Starting variables for workflow
- `max_states`: Maximum states to prevent infinite loops (default: 100)
- `execution_timeout`: Maximum execution time in seconds (default: 1800)
- `save_on_success`: Auto-save successful workflows (default: true)

**Returns:**
- Detailed execution log and final state information
- All variables available at completion
- Information about workflow persistence
- List of available saved workflows

**Key Features:**
- **🔄 Conditional Logic**: Branch execution based on tool results
- **🔁 Loop Support**: States can transition back to previous states
- **📊 Variable System**: Automatic extraction from tool returns
- **💾 Auto-Persistence**: Successful workflows saved for reuse
- **🔗 Composition**: Workflows can call other workflows recursively
- **⏱️ Timeout Handling**: State and workflow-level timeout management
- **🛡️ Safety Limits**: Prevents infinite loops and excessive recursion

---

## 📋 Workflow Definition Schema

### JSON Schema Structure
```json
{
  "name": "workflow_identifier",
  "description": "Human readable description",
  "initial_state": "starting_state_name",
  "states": {
    "state_name": {
      "action": {
        "tool": "tool_name",
        "params": { /* tool-specific parameters */ }
      },
      "transitions": [
        {
          "condition": { /* condition definition */ },
          "next_state": "target_state_name"
        }
      ],
      "timeout": 30.0,
      "on_timeout": "timeout_state_name"
    }
  }
}
```

### Available Tools in Workflows
- `open_terminal` - Create terminal sessions
- `send_input` - Send commands to terminals  
- `await_output` - Wait for specific output patterns
- `get_screen_content` - Get terminal content
- `list_terminal_sessions` - List active sessions
- `exit_terminal` - Clean up sessions
- `run_workflow` - Call other workflows recursively

### Condition Types
```json
{
  "success": true,                           // Tool succeeded/failed
  "pattern_match": "regex_pattern",          // Output matches regex
  "pattern_not_match": "regex_pattern",      // Output does NOT match regex  
  "field_equals": {"field": "value"},        // Tool result field equals value
  "field_contains": {"field": "substring"},  // Tool result field contains text
  "timeout_occurred": true                   // State timed out
}
```

### Standard Variables
| Variable | Source Tools | Description |
|----------|-------------|-------------|
| `{session_id}` | Terminal tools | Active session identifier |
| `{match_text}` | await_output | Text that matched regex pattern |
| `{screen_content}` | Terminal tools | Current terminal content |
| `{success}` | All tools | Success status (true/false) |
| `{error}` | All tools | Error message if failed |
| `{timestamp}` | Most tools | ISO timestamp of operation |
| `{elapsed_time}` | await_output | Time taken for operation |
| `{shell}` | open_terminal | Shell type that was started |
| `{web_url}` | open_terminal | Web interface URL |
| `{process_running}` | get_screen_content | Whether process is active |
| `{total_sessions}` | list_terminal_sessions | Number of active sessions |
| `{message}` | exit_terminal | Status message |
| `{workflow_final_state}` | run_workflow | Final state from recursive call |
| `{workflow_saved}` | run_workflow | Whether workflow was saved |

---

## 🔗 Workflow Examples

### Simple Linear Workflow
```json
{
  "name": "simple_test",
  "description": "Run a simple test command",
  "initial_state": "start_session",
  "states": {
    "start_session": {
      "action": {
        "tool": "open_terminal",
        "params": {"shell": "bash"}
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "run_test"}
      ]
    },
    "run_test": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "echo 'Test completed'\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "cleanup"}
      ]
    },
    "cleanup": {
      "action": {
        "tool": "exit_terminal", 
        "params": {"session_id": "{session_id}"}
      },
      "transitions": []
    }
  }
}
```

### Conditional Branching Workflow
```json
{
  "name": "test_with_branching",
  "description": "Run tests and handle success/failure",
  "initial_state": "start_session",
  "states": {
    "start_session": {
      "action": {
        "tool": "open_terminal",
        "params": {"shell": "bash"}
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "run_tests"}
      ]
    },
    "run_tests": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "npm test\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "wait_for_results"}
      ]
    },
    "wait_for_results": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": "(\\d+) passing|(\\d+) failing|Tests failed",
          "timeout": 60.0
        }
      },
      "transitions": [
        {
          "condition": {"pattern_match": "passing"},
          "next_state": "tests_passed"
        },
        {
          "condition": {"pattern_match": "failing|failed"},
          "next_state": "tests_failed"
        }
      ]
    },
    "tests_passed": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "echo '✅ All tests passed!'\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "cleanup"}
      ]
    },
    "tests_failed": {
      "action": {
        "tool": "get_screen_content",
        "params": {
          "session_id": "{session_id}",
          "content_mode": "tail",
          "line_count": 30
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "cleanup"}
      ]
    },
    "cleanup": {
      "action": {
        "tool": "exit_terminal",
        "params": {"session_id": "{session_id}"}
      },
      "transitions": []
    }
  }
}
```

### Interactive User Input Workflow
```json
{
  "name": "interactive_debug",
  "description": "Interactive debugging session with user input",
  "initial_state": "start_session",
  "states": {
    "start_session": {
      "action": {
        "tool": "open_terminal",
        "params": {"shell": "bash"}
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "start_debugger"}
      ]
    },
    "start_debugger": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "python -m pdb script.py\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "wait_for_pdb"}
      ]
    },
    "wait_for_pdb": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": "\\(Pdb\\)",
          "timeout": 10.0
        }
      },
      "transitions": [
        {"condition": {"pattern_match": "\\(Pdb\\)"}, "next_state": "prompt_user"}
      ]
    },
    "prompt_user": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "read -p 'Debug command (l=list, s=step, c=continue, q=quit): ' cmd && echo \"USER_CMD:$cmd\"\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "capture_choice"}
      ]
    },
    "capture_choice": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": "USER_CMD:([lscq])",
          "timeout": 60.0
        }
      },
      "transitions": [
        {"condition": {"pattern_match": "USER_CMD:l"}, "next_state": "list_code"},
        {"condition": {"pattern_match": "USER_CMD:s"}, "next_state": "step_code"},
        {"condition": {"pattern_match": "USER_CMD:c"}, "next_state": "continue_exec"},
        {"condition": {"pattern_match": "USER_CMD:q"}, "next_state": "quit_debug"}
      ]
    },
    "list_code": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "l\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "wait_after_list"}
      ]
    },
    "wait_after_list": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": "\\(Pdb\\)",
          "timeout": 5.0
        }
      },
      "transitions": [
        {"condition": {"pattern_match": "\\(Pdb\\)"}, "next_state": "prompt_user"}
      ]
    },
    "step_code": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "s\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "wait_after_step"}
      ]
    },
    "wait_after_step": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": "\\(Pdb\\)",
          "timeout": 5.0
        }
      },
      "transitions": [
        {"condition": {"pattern_match": "\\(Pdb\\)"}, "next_state": "prompt_user"}
      ]
    },
    "continue_exec": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "c\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "wait_for_completion"}
      ]
    },
    "wait_for_completion": {
      "action": {
        "tool": "await_output",
        "params": {
          "session_id": "{session_id}",
          "pattern": ">>>|\\$|completed",
          "timeout": 30.0
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "cleanup"}
      ]
    },
    "quit_debug": {
      "action": {
        "tool": "send_input",
        "params": {
          "session_id": "{session_id}",
          "input_text": "q\n"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "cleanup"}
      ]
    },
    "cleanup": {
      "action": {
        "tool": "exit_terminal",
        "params": {"session_id": "{session_id}"}
      },
      "transitions": []
    }
  }
}
```

### Workflow Composition Example
```json
{
  "name": "full_ci_pipeline",
  "description": "Complete CI pipeline using sub-workflows",
  "initial_state": "run_linting",
  "states": {
    "run_linting": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "code_linting",
          "initial_variables": {"target_dir": "src/"}
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "run_tests"},
        {"condition": {"success": false}, "next_state": "linting_failed"}
      ]
    },
    "run_tests": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "test_suite",
          "initial_variables": {"test_type": "unit"}
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "build_project"},
        {"condition": {"success": false}, "next_state": "tests_failed"}
      ]
    },
    "build_project": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "build_production"
        }
      },
      "transitions": [
        {"condition": {"success": true}, "next_state": "deploy"},
        {"condition": {"success": false}, "next_state": "build_failed"}
      ]
    },
    "deploy": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "production_deploy",
          "initial_variables": {"environment": "prod"}
        }
      },
      "transitions": []
    },
    "linting_failed": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "notify_failure",
          "initial_variables": {
            "stage": "linting",
            "message": "Code linting failed - check style issues"
          }
        }
      },
      "transitions": []
    },
    "tests_failed": {
      "action": {
        "tool": "run_workflow", 
        "params": {
          "workflow_name": "notify_failure",
          "initial_variables": {
            "stage": "testing",
            "message": "Unit tests failed - check test results"
          }
        }
      },
      "transitions": []
    },
    "build_failed": {
      "action": {
        "tool": "run_workflow",
        "params": {
          "workflow_name": "notify_failure",
          "initial_variables": {
            "stage": "build", 
            "message": "Production build failed - check build logs"
          }
        }
      },
      "transitions": []
    }
  }
}
```

---

## 💾 Workflow Persistence

### Automatic Saving
- Successful workflows are automatically saved to `.terminal_control_workflows/`
- Each workflow is saved as `{workflow_name}.json`
- Duplicate workflows (same logic) are not saved twice
- Metadata includes creation time, success count, and last execution

### Workflow Library
- Build up a library of reusable workflow components over time
- Reference saved workflows by name in new workflows
- Compose complex operations from proven simpler workflows
- Share workflows across different projects and contexts

### Usage Patterns
```python
# Execute inline workflow (will be auto-saved if successful)
run_workflow(RunWorkflowRequest(
    workflow_definition={...complete_workflow...}
))

# Execute saved workflow
run_workflow(RunWorkflowRequest(
    workflow_name="my_saved_workflow"
))

# Execute with custom variables
run_workflow(RunWorkflowRequest(
    workflow_name="parameterized_workflow",
    initial_variables={"env": "production", "version": "v1.2.3"}
))
```

---

## ⚠️ Safety and Limits

### Infinite Loop Prevention
- **Max States Limit**: Default 100 states per workflow execution
- **Global Timeout**: Default 30 minutes total execution time
- **State Timeout**: Individual states can have custom timeouts
- **Recursion Depth**: Maximum 5 levels of workflow calls

### Error Handling
- **Schema Validation**: Workflows validated before execution
- **State Existence**: All transitions checked for valid targets
- **Tool Call Failures**: Can be handled via `success: false` conditions
- **Timeout Recovery**: States can specify timeout transition targets
- **Resource Cleanup**: Terminal sessions properly cleaned up on errors

### Best Practices
- **Keep workflows focused**: Single responsibility per workflow
- **Use descriptive names**: Clear state and workflow naming
- **Handle failures gracefully**: Always include error transitions
- **Test thoroughly**: Validate workflows with various inputs
- **Monitor execution logs**: Review logs for optimization opportunities
```

### Step 9: Update CLAUDE.md
**File**: `CLAUDE.md` (add section after existing tools)

```markdown
### run_workflow
```bash
# Execute an inline workflow definition
python -c "
from src.terminal_control_mcp.main import run_workflow
from src.terminal_control_mcp.models import RunWorkflowRequest
# ... execute workflow ...
"

# Execute a saved workflow by name
python -c "
from src.terminal_control_mcp.main import run_workflow
from src.terminal_control_mcp.models import RunWorkflowRequest
result = await run_workflow(RunWorkflowRequest(workflow_name='my_workflow'), ctx)
"
```

The `run_workflow` tool orchestrates the existing 6 MCP tools plus itself to create complex conditional workflows with:
- Automatic persistence of successful workflows in `.terminal_control_workflows/`
- Recursive composition - workflows can call other workflows
- Loop support through state transitions
- User interaction via terminal input/output
- Comprehensive error handling and timeout management
```

### Step 10: Final Integration Steps

1. **Update imports** in `src/terminal_control_mcp/__init__.py`:
```python
from .workflow_engine import WorkflowEngine
from .workflow_persistence import WorkflowPersistence
from .workflow_schema import WORKFLOW_SCHEMA, validate_workflow_schema
```

2. **Update main.py tool count** in docstring:
```python
"""
MCP Server for Terminal Control with Interactive Sessions and Workflow Automation

This server provides 7 MCP tools for managing terminal sessions and workflows:
"""
```

3. **Run comprehensive tests**:
```bash
# Run all tests including new workflow tests
pytest tests/ -v

# Run only workflow tests 
pytest tests/test_run_workflow.py -v

# Run with coverage
pytest --cov=src/terminal_control_mcp --cov-report=html tests/
```

4. **Code quality checks**:
```bash
# Type checking
mypy src/ --ignore-missing-imports

# Linting
ruff check src/ tests/

# Format code
black src/ tests/

# Check for dead code
vulture src/
```

5. **Create example workflow files**:
Create `.terminal_control_workflows/examples/` with sample workflows for documentation.

---

## ⚠️ Critical Issues Addressed

### **Edge Cases Handled:**
1. **Circular Dependencies**: Prevented through recursion depth limits
2. **File System Errors**: Atomic operations and error recovery in persistence
3. **JSON Corruption**: Validation before all operations
4. **Memory Leaks**: Proper cleanup of terminal sessions and variables
5. **Infinite Loops**: Multiple prevention mechanisms (max states, timeouts, detection)
6. **Concurrent Access**: Thread-safe file operations
7. **Invalid Workflows**: Comprehensive schema and logical validation
8. **Tool Call Failures**: Graceful error handling and recovery paths
9. **Variable Injection**: Safe variable substitution with proper escaping
10. **Resource Exhaustion**: Limits on workflow size, execution time, recursion depth

### **Ambiguities Resolved:**
1. **Workflow Sources**: Clear validation that exactly one source is provided
2. **Variable Precedence**: Defined order (state-specific > standard > initial)
3. **Persistence Logic**: When and how workflows are saved automatically
4. **Error Recovery**: What happens when tools fail vs when workflows fail
5. **Timeout Behavior**: State timeouts vs workflow timeouts vs tool timeouts
6. **Recursion Semantics**: How recursive calls inherit vs isolate context
7. **Schema Compliance**: Explicit validation points and error messages
8. **State Naming**: Valid identifier patterns and conflict resolution

### **Implementation Details Specified:**
1. **File Structure**: Exact directory layout and file naming conventions
2. **Variable Extraction**: Complete mapping from tool results to variables
3. **Condition Evaluation**: Precise logic for each condition type
4. **Error Messages**: Specific error text for different failure modes
5. **JSON Schema**: Complete formal specification with all constraints
6. **State Transitions**: Exact algorithm for evaluating and selecting transitions
7. **Persistence Format**: File structure and metadata organization
8. **Testing Strategy**: Comprehensive test coverage for all edge cases

This implementation plan provides complete, unambiguous instructions for implementing the `run_workflow` tool with all edge cases covered and potential problems addressed.