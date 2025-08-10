# TODO: Implement Workflow System - Agent-Controlled Terminal Automation

## Overview
Extend the existing terminal-control-mcp server with workflow automation capabilities. Add two new MCP tools: `create_workflow` for workflow definition/validation/storage, and `run_workflow` for execution with environment variable validation. Agents control all environment variables through terminal commands, while the system validates workflow contracts.

## Key Features  
- **Agent-Controlled Environment**: Agents handle environment variables via terminal commands (export/echo)
- **Contract Validation**: Strict validation of required arguments before execution and return values after execution
- **Workflow Signatures**: Clear contracts defining input/output environment variables with descriptions
- **Terminal-First Design**: Workflows execute within existing terminal sessions using current MCP tools
- **Fail-Fast Validation**: Workflows fail immediately if required environment variables are missing

## Agent Workflow Process with Validation

Agents follow a validated 4-step process:

1. **Create/Understand Workflow Contract**
   ```python
   # System validates workflow definition and returns signature
   response = await create_workflow({
       "workflow_definition": {
           "name": "build_project",
           "arguments": {"PROJECT_ROOT": "Path to project directory"},
           "return_values": {"BUILD_STATUS": "Success/failure status", "BUILD_OUTPUT": "Build logs"}
       }
   })
   ```

2. **Set Required Environment Variables (validated before execution)**
   ```bash
   export PROJECT_ROOT="/path/to/project"
   ```

3. **Run Workflow (fails if required env vars missing)**
   ```python
   # System checks PROJECT_ROOT exists before starting
   await run_workflow({
       "workflow_name": "build_project",
       "session_id": "current_session"
   })
   ```

4. **Verify Return Values (validated after execution)**
   ```bash
   echo $BUILD_STATUS  # System ensures this was set
   echo $BUILD_OUTPUT  # System ensures this was set
   ```

The system enforces the workflow contract at both boundaries - failing fast if inputs are missing and failing if expected outputs weren't produced.

## Implementation Steps

### Step 1: JSON Schema Generation and MCP Tool Introspection
**File**: `src/terminal_control_mcp/workflow_schema.py`

```python
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import inspect
import json
from datetime import datetime

def introspect_mcp_tools() -> Dict[str, Dict[str, Any]]:
    """Introspect actual MCP server tools to generate schema automatically"""
    from . import main
    
    tools = {}
    
    # Get all functions decorated with @mcp.tool()
    for name in dir(main):
        obj = getattr(main, name)
        if callable(obj) and hasattr(obj, '__annotations__'):
            # Check if it's an MCP tool by looking for specific patterns
            if name in ['open_terminal', 'send_input', 'get_screen_content', 
                       'await_output', 'list_terminal_sessions', 'exit_terminal']:
                
                # Extract parameter info from function signature
                sig = inspect.signature(obj)
                params = {}
                
                for param_name, param in sig.parameters.items():
                    if param_name in ['ctx', 'context']:  # Skip context parameters
                        continue
                    
                    # Extract parameter type and info from request model
                    if hasattr(param.annotation, '__fields__'):
                        request_model = param.annotation
                        for field_name, field_info in request_model.model_fields.items():
                            if field_name != 'session_id':  # session_id auto-injected
                                params[field_name] = {
                                    'type': str(field_info.annotation),
                                    'description': field_info.description or '',
                                    'required': field_info.is_required(),
                                    'default': field_info.default if field_info.default is not None else None
                                }
                
                tools[name] = {
                    'description': obj.__doc__.split('\n')[0] if obj.__doc__ else '',
                    'parameters': params,
                    'returns_success': True,  # All MCP tools return success field
                    'supports_timeout': name == 'await_output'
                }
    
    return tools

def generate_workflow_json_schema() -> Dict[str, Any]:
    """Generate definitive JSON schema for workflow definitions"""
    
    # Get available tools dynamically
    available_tools = list(introspect_mcp_tools().keys())
    
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Workflow Definition",
        "description": "Terminal Control MCP Server Workflow Definition with Environment Variable Contracts",
        "type": "object",
        "required": ["name", "description", "initial_state", "states"],
        "properties": {
            "name": {
                "type": "string",
                "pattern": "^[a-z0-9_]+$",
                "minLength": 1,
                "maxLength": 64,
                "description": "Unique workflow identifier (lowercase, underscores only)"
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "maxLength": 500,
                "description": "Human-readable description of workflow purpose"
            },
            "arguments": {
                "type": "object",
                "maxProperties": 20,
                "description": "Required input environment variables",
                "patternProperties": {
                    "^[A-Z][A-Z0-9_]*$": {
                        "type": "object",
                        "required": ["name", "description"],
                        "properties": {
                            "name": {
                                "type": "string",
                                "pattern": "^[A-Z][A-Z0-9_]*$"
                            },
                            "description": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 200
                            },
                            "required": {
                                "type": "boolean",
                                "default": True
                            }
                        }
                    }
                },
                "additionalProperties": False
            },
            "return_values": {
                "type": "object",
                "maxProperties": 20,
                "description": "Environment variables the workflow must set",
                "patternProperties": {
                    "^[A-Z][A-Z0-9_]*$": {
                        "type": "object",
                        "required": ["name", "description"],
                        "properties": {
                            "name": {
                                "type": "string",
                                "pattern": "^[A-Z][A-Z0-9_]*$"
                            },
                            "description": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 200
                            },
                            "required": {
                                "type": "boolean",
                                "default": True
                            }
                        }
                    }
                },
                "additionalProperties": False
            },
            "initial_state": {
                "type": "string",
                "description": "Name of the starting state"
            },
            "states": {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 50,
                "description": "State machine definition",
                "patternProperties": {
                    "^[a-z0-9_]+$": {
                        "type": "object",
                        "required": ["action"],
                        "properties": {
                            "action": {
                                "type": "object",
                                "required": ["tool"],
                                "properties": {
                                    "tool": {
                                        "type": "string",
                                        "enum": available_tools,
                                        "description": f"MCP tool to execute. Available: {', '.join(available_tools)}"
                                    },
                                    "params": {
                                        "type": "object",
                                        "description": "Tool parameters (session_id auto-injected)",
                                        "additionalProperties": True
                                    }
                                },
                                "additionalProperties": False
                            },
                            "transitions": {
                                "type": "array",
                                "maxItems": 5,
                                "description": "Conditional state transitions",
                                "items": {
                                    "type": "object",
                                    "required": ["condition", "next_state"],
                                    "properties": {
                                        "condition": {
                                            "type": "string",
                                            "enum": ["success", "failure", "timeout", "pattern_match", "pattern_no_match"],
                                            "description": "Transition condition based on MCP tool result"
                                        },
                                        "next_state": {
                                            "type": "string",
                                            "pattern": "^[a-z0-9_]+$",
                                            "description": "Target state name"
                                        },
                                        "pattern": {
                                            "type": "string",
                                            "description": "Regex pattern (required for pattern_match/pattern_no_match)"
                                        }
                                    },
                                    "additionalProperties": False,
                                    "if": {
                                        "properties": {
                                            "condition": {"enum": ["pattern_match", "pattern_no_match"]}
                                        }
                                    },
                                    "then": {
                                        "required": ["condition", "next_state", "pattern"]
                                    }
                                }
                            },
                            "timeout_seconds": {
                                "type": "number",
                                "minimum": 0.1,
                                "maximum": 300.0,
                                "description": "Timeout for this state's action"
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            }
        },
        "additionalProperties": False
    }
    
    return schema

def get_workflow_schema_documentation() -> str:
    """Generate formatted documentation for workflow schema"""
    tools_info = introspect_mcp_tools()
    schema = generate_workflow_json_schema()
    
    doc = f"""
## Workflow Definition JSON Schema

Generated automatically from MCP server tools on {datetime.now().isoformat()}

### Available MCP Tools:
"""
    
    for tool_name, tool_info in tools_info.items():
        doc += f"""
**{tool_name}**: {tool_info['description']}
"""
        if tool_info['parameters']:
            doc += "Parameters:\n"
            for param, info in tool_info['parameters'].items():
                required = "(required)" if info['required'] else "(optional)"
                doc += f"  - {param}: {info['description']} {required}\n"
    
    doc += f"""

### JSON Schema:
```json
{json.dumps(schema, indent=2)}
```

### State Machine Transitions:
- **success**: Execute when MCP tool returns success=True
- **failure**: Execute when MCP tool returns success=False or has error
- **timeout**: Execute when await_output tool times out (match_text=None)
- **pattern_match**: Execute when regex pattern matches current screen content
- **pattern_no_match**: Execute when regex pattern does NOT match screen content

### Environment Variable Contract:
- **arguments**: Environment variables that MUST be set before workflow execution
- **return_values**: Environment variables that workflow MUST set during execution
- Variable names must be UPPERCASE with underscores only
- Both arguments and return values are validated automatically
"""
    
    return doc
```

### Step 2: Workflow Models with Environment Variable Validation
**File**: `src/terminal_control_mcp/workflow_models.py`

```python
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, model_validator
import re

class WorkflowAction(BaseModel):
    """Workflow action that calls an existing MCP tool"""
    tool: str = Field(..., description="MCP tool name (open_terminal, send_input, get_screen_content, await_output, list_terminal_sessions, exit_terminal)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters - session_id will be auto-injected if not provided")
    
    @model_validator(mode='after')
    def validate_tool_name(self):
        """Validate tool name against existing MCP tools"""
        valid_tools = {
            "open_terminal", "send_input", "get_screen_content", 
            "await_output", "list_terminal_sessions", "exit_terminal"
        }
        if self.tool not in valid_tools:
            raise ValueError(f"Tool '{self.tool}' not supported. Available tools: {', '.join(sorted(valid_tools))}")
        return self

class WorkflowCondition(BaseModel):
    """Condition for state transitions (agent evaluates manually)"""
    description: str = Field(..., max_length=200, description="Human-readable description of condition to check")

class WorkflowTransition(BaseModel):
    """State transition definition"""
    condition: WorkflowCondition = Field(..., description="Condition to evaluate")
    next_state: str = Field(..., description="Target state name")

class WorkflowState(BaseModel):
    """Individual workflow state definition"""
    action: WorkflowAction = Field(..., description="Action to execute in this state")
    transitions: List[WorkflowTransition] = Field(default_factory=list, max_length=10, description="Possible transitions from this state")

class EnvironmentVariable(BaseModel):
    """Environment variable definition with validation"""
    name: str = Field(..., min_length=1, max_length=64, description="Environment variable name")
    description: str = Field(..., min_length=1, max_length=200, description="Description of the variable's purpose and expected format")
    required: bool = Field(True, description="Whether this variable is mandatory")
    
    @model_validator(mode='after')
    def validate_env_var_name(self):
        """Validate environment variable name format"""
        if not re.match(r'^[A-Z][A-Z0-9_]*$', self.name):
            raise ValueError(f"Environment variable '{self.name}' must be uppercase, start with letter, contain only letters, numbers, and underscores")
        return self

class WorkflowDefinition(BaseModel):
    """Complete workflow definition with validated environment variable contract"""
    name: str = Field(..., min_length=1, max_length=64, description="Workflow identifier")
    description: str = Field(..., min_length=1, max_length=500, description="Human-readable workflow description")
    arguments: Dict[str, EnvironmentVariable] = Field(default_factory=dict, max_length=20, description="Required input environment variables")
    return_values: Dict[str, EnvironmentVariable] = Field(default_factory=dict, max_length=20, description="Environment variables the workflow must set")
    initial_state: str = Field(..., description="Starting state name")
    states: Dict[str, WorkflowState] = Field(..., min_length=1, max_length=50, description="State definitions")
    
    @model_validator(mode='after')
    def validate_workflow_structure(self):
        """Comprehensive workflow validation"""
        # Validate initial state exists
        if self.initial_state not in self.states:
            raise ValueError(f"Initial state '{self.initial_state}' not found in states")
        
        # Validate all transition targets exist
        for state_name, state in self.states.items():
            for transition in state.transitions:
                if transition.next_state not in self.states:
                    raise ValueError(f"State '{state_name}' transition target '{transition.next_state}' not found")
        
        # Validate workflow name format
        if not re.match(r'^[a-z0-9_]+$', self.name):
            raise ValueError(f"Workflow name '{self.name}' must be lowercase with only letters, numbers, and underscores")
        
        # Ensure no duplicate environment variable names between arguments and return values
        arg_names = set(self.arguments.keys())
        return_names = set(self.return_values.keys())
        overlap = arg_names.intersection(return_names)
        if overlap:
            raise ValueError(f"Environment variables cannot be both arguments and return values: {', '.join(overlap)}")
        
        return self
```

### Step 2: Workflow Storage with Modern Python Patterns
**File**: `src/terminal_control_mcp/workflow_storage.py`

```python
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from .workflow_models import WorkflowDefinition

logger = logging.getLogger(__name__)

class WorkflowStorage:
    """Workflow storage with validation and proper error handling"""
    
    def __init__(self, workflows_dir: str = ".terminal_control_workflows"):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(exist_ok=True)
        self.index_file = self.workflows_dir / ".index.jsonl"
        self._ensure_index_exists()
    
    def _ensure_index_exists(self) -> None:
        """Create index file if it doesn't exist"""
        if not self.index_file.exists():
            self.index_file.write_text("", encoding="utf-8")
    
    def store_workflow(self, workflow_def: Dict[str, Any]) -> str:
        """Store validated workflow and update index"""
        # Validate workflow definition first
        validated_workflow = WorkflowDefinition(**workflow_def)
        workflow_name = validated_workflow.name
        
        # Create workflow file with metadata
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        workflow_data = {
            "definition": validated_workflow.model_dump(),
            "metadata": {
                "created": datetime.now(timezone.utc).isoformat(),
                "run_count": 0,
                "last_run": None,
                "version": "1.0"
            }
        }
        
        workflow_file.write_text(json.dumps(workflow_data, indent=2), encoding="utf-8")
        logger.info(f"Stored workflow '{workflow_name}' to {workflow_file}")
        
        # Update index with environment variable contract info
        index_entry = {
            "name": workflow_name,
            "file": f"{workflow_name}.json", 
            "description": validated_workflow.description,
            "arguments": {name: var.model_dump() for name, var in validated_workflow.arguments.items()},
            "return_values": {name: var.model_dump() for name, var in validated_workflow.return_values.items()},
            "created": workflow_data["metadata"]["created"],
            "run_count": 0,
            "last_run": None,
            "state_count": len(validated_workflow.states)
        }
        
        # Remove existing entry if updating
        self._remove_from_index(workflow_name)
        
        # Add new entry
        with open(self.index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(index_entry) + "\n")
        
        return workflow_name
    
    def _remove_from_index(self, workflow_name: str) -> None:
        """Remove workflow entry from index"""
        if not self.index_file.exists():
            return
        
        # Read all entries except the one to remove
        remaining_entries = []
        with open(self.index_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line.strip())
                    if entry.get("name") != workflow_name:
                        remaining_entries.append(entry)
        
        # Rewrite index
        with open(self.index_file, "w", encoding="utf-8") as f:
            for entry in remaining_entries:
                f.write(json.dumps(entry) + "\n")
    
    def load_workflow(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Load and validate workflow definition by name"""
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        if not workflow_file.exists():
            logger.warning(f"Workflow file not found: {workflow_file}")
            return None
        
        try:
            workflow_data = json.loads(workflow_file.read_text(encoding="utf-8"))
            definition = workflow_data.get("definition")
            
            # Validate on load
            WorkflowDefinition(**definition)
            return definition
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load workflow '{workflow_name}': {e}")
            return None
    
    def update_run_stats(self, workflow_name: str) -> None:
        """Update workflow execution statistics"""
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        if not workflow_file.exists():
            logger.warning(f"Cannot update stats for non-existent workflow: {workflow_name}")
            return
        
        try:
            workflow_data = json.loads(workflow_file.read_text(encoding="utf-8"))
            workflow_data["metadata"]["run_count"] += 1
            workflow_data["metadata"]["last_run"] = datetime.now(timezone.utc).isoformat()
            
            workflow_file.write_text(json.dumps(workflow_data, indent=2), encoding="utf-8")
            logger.info(f"Updated run stats for workflow '{workflow_name}'")
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to update stats for '{workflow_name}': {e}")
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """Get list of all stored workflows with contract information"""
        if not self.index_file.exists():
            return []
        
        workflows = []
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            workflows.append(json.loads(line.strip()))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping malformed index line {line_num}: {e}")
        except IOError as e:
            logger.error(f"Failed to read workflow index: {e}")
        
        return workflows
    
    def get_workflow_info(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Get workflow metadata with environment variable contract"""
        workflows = self.list_workflows()
        for workflow in workflows:
            if workflow.get("name") == workflow_name:
                return workflow
        return None
    
    def delete_workflow(self, workflow_name: str) -> bool:
        """Delete workflow and remove from index"""
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        
        try:
            if workflow_file.exists():
                workflow_file.unlink()
                logger.info(f"Deleted workflow file: {workflow_file}")
            
            self._remove_from_index(workflow_name)
            logger.info(f"Removed workflow '{workflow_name}' from index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete workflow '{workflow_name}': {e}")
            return False
```

### Step 3: Example Workflow Definitions with Environment Variable Contracts

Example workflow showing the complete environment variable validation pattern:

**Build Project Workflow:**
```json
{
  "name": "build_project",
  "description": "Build a software project with validation and status reporting",
  "arguments": {
    "PROJECT_ROOT": {
      "name": "PROJECT_ROOT",
      "description": "Absolute path to the project root directory",
      "required": true
    },
    "BUILD_TYPE": {
      "name": "BUILD_TYPE",
      "description": "Build type: debug, release, or test",
      "required": true
    }
  },
  "return_values": {
    "BUILD_STATUS": {
      "name": "BUILD_STATUS",
      "description": "Build result: SUCCESS, FAILED, or ERROR",
      "required": true
    },
    "BUILD_OUTPUT": {
      "name": "BUILD_OUTPUT",
      "description": "Path to build output directory or error message",
      "required": true
    },
    "BUILD_TIME": {
      "name": "BUILD_TIME",
      "description": "Build duration in seconds",
      "required": false
    }
  },
  "initial_state": "start_build",
  "states": {
    "start_build": {
      "action": {
        "tool": "send_input",
        "params": {
          "input_text": "cd $PROJECT_ROOT && echo 'Starting build...' && make $BUILD_TYPE && echo 'Build completed'\n"
        }
      },
      "transitions": [
        {
          "condition": {
            "description": "Check if build completed successfully"
          },
          "next_state": "set_results"
        }
      ]
    },
    "set_results": {
      "action": {
        "tool": "send_input",
        "params": {
          "input_text": "export BUILD_STATUS=SUCCESS && export BUILD_OUTPUT=/path/to/build && export BUILD_TIME=45\n"
        }
      },
      "transitions": []
    }
  }
}
```

**Agent Usage Pattern:**
```bash
# 1. Set required arguments
export PROJECT_ROOT="/home/user/myproject"
export BUILD_TYPE="release"

# 2. Run workflow (validates arguments first)
# run_workflow(workflow_name="build_project", session_id="session123")

# 3. Check return values (validated after execution)
echo "Build status: $BUILD_STATUS"
echo "Build output: $BUILD_OUTPUT"
echo "Build time: $BUILD_TIME"
```

```python
class CreateWorkflowRequest(BaseModel):
    """Request to create and store a workflow"""
    workflow_definition: Dict[str, Any] = Field(..., description="Complete workflow definition")
    overwrite_existing: bool = Field(default=False, description="Whether to overwrite existing workflow with same name")

class CreateWorkflowResponse(BaseModel):
    """Response from workflow creation"""
    success: bool
    workflow_name: str
    stored_file: str
    workflow_signature: Dict[str, Any] = Field(description="Arguments and return values the agent needs to know about")
    validation_errors: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class RunWorkflowRequest(BaseModel):
    """Request to execute a stored workflow"""
    workflow_name: str = Field(..., description="Name of workflow file (without .json extension)")
    session_id: str = Field(..., description="Terminal session ID to run workflow in")

class RunWorkflowResponse(BaseModel):
    """Response from workflow execution"""
    success: bool
    workflow_name: str
    session_id: str = Field(description="Terminal session ID workflow ran in")
    final_state: str
    states_executed: int  
    workflow_signature: Dict[str, Any] = Field(description="Arguments and return values for reference")
    execution_log: List[Dict[str, Any]] = Field(description="Execution log")
    error: Optional[str] = None
```

### Step 4: Workflow Execution Engine with Environment Variable Validation
**File**: `src/terminal_control_mcp/workflow_execution.py`

```python
import asyncio
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timezone
import re

if TYPE_CHECKING:
    from .main import AppContext

async def validate_environment_variables(
    session_id: str,
    required_vars: Dict[str, Any],
    app_ctx: "AppContext",
    validation_type: str = "arguments"
) -> Dict[str, Any]:
    """Validate required environment variables exist in session"""
    from .main import send_input, get_screen_content
    from .models import SendInputRequest, GetScreenContentRequest
    from types import SimpleNamespace
    
    mock_ctx = SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=app_ctx)
    )
    
    missing_vars = []
    validation_log = []
    
    for var_name, var_def in required_vars.items():
        # Check if environment variable exists
        check_cmd = f"echo \"CHECKING_{var_name}: ${{${var_name}+SET}}\"\n"
        
        # Send check command
        send_req = SendInputRequest(session_id=session_id, input_text=check_cmd)
        await send_input(send_req, mock_ctx)
        
        # Get result
        get_req = GetScreenContentRequest(session_id=session_id, content_mode="since_input")
        result = await get_screen_content(get_req, mock_ctx)
        
        # Check if variable is set
        if result.screen_content and f"CHECKING_{var_name}: SET" in result.screen_content:
            validation_log.append({"variable": var_name, "status": "present", "required": var_def.get('required', True)})
        else:
            if var_def.get('required', True):
                missing_vars.append(var_name)
            validation_log.append({"variable": var_name, "status": "missing", "required": var_def.get('required', True)})
    
    return {
        "valid": len(missing_vars) == 0,
        "missing_vars": missing_vars,
        "validation_log": validation_log,
        "validation_type": validation_type
    }

async def execute_workflow(
    workflow_def: Dict[str, Any],
    session_id: str,
    app_ctx: "AppContext"
) -> Dict[str, Any]:
    """Execute workflow with environment variable validation"""
    
    execution_log = []
    
    try:
        # PRE-EXECUTION VALIDATION: Check required argument environment variables
        if workflow_def.get("arguments"):
            arg_validation = await validate_environment_variables(
                session_id, 
                workflow_def["arguments"], 
                app_ctx, 
                "arguments"
            )
            execution_log.append({
                "phase": "pre_execution_validation",
                "validation_result": arg_validation,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            if not arg_validation["valid"]:
                return {
                    "success": False,
                    "final_state": "validation_failed",
                    "states_executed": 0,
                    "execution_log": execution_log,
                    "error": f"Missing required environment variables: {', '.join(arg_validation['missing_vars'])}. Set them with: {', '.join([f'export {var}=value' for var in arg_validation['missing_vars']])}"
                }
        
        # WORKFLOW EXECUTION
        current_state = workflow_def["initial_state"]
        states_executed = 0
        
        while current_state and states_executed < 100:  # Loop protection
            if current_state not in workflow_def["states"]:
                raise ValueError(f"State '{current_state}' not found")
            
            state_def = workflow_def["states"][current_state]
            
            # Execute state action
            tool_result = await _call_mcp_tool(
                state_def["action"]["tool"],
                state_def["action"]["params"],
                session_id,
                app_ctx
            )
            
            states_executed += 1
            
            # Log execution
            log_entry = {
                "phase": "execution",
                "state": current_state,
                "tool": state_def["action"]["tool"],
                "params": state_def["action"]["params"],
                "result": _serialize_result(tool_result),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            execution_log.append(log_entry)
            
            # STATE MACHINE EXECUTION: Handle conditional transitions based on tool results
            transitions_evaluated = 0
            max_transitions = 50  # Prevent infinite loops
            
            while current_state and transitions_evaluated < max_transitions:
                if current_state not in workflow_def["states"]:
                    raise ValueError(f"State '{current_state}' not found")
                
                state_def = workflow_def["states"][current_state]
                
                # Execute state action
                tool_result = await _call_mcp_tool(
                    state_def["action"]["tool"],
                    state_def["action"]["params"],
                    session_id,
                    app_ctx
                )
                
                states_executed += 1
                
                # Determine tool execution result
                tool_success = _evaluate_tool_result(state_def["action"]["tool"], tool_result)
                
                # Log execution with result evaluation
                log_entry = {
                    "phase": "execution",
                    "state": current_state,
                    "tool": state_def["action"]["tool"],
                    "params": state_def["action"]["params"],
                    "result": _serialize_result(tool_result),
                    "tool_success": tool_success,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                execution_log.append(log_entry)
                
                # Evaluate state transitions
                next_state = await _evaluate_state_transitions(
                    state_def["transitions"],
                    tool_result,
                    tool_success,
                    session_id,
                    app_ctx
                )
                
                if next_state:
                    execution_log.append({
                        "phase": "transition",
                        "from_state": current_state,
                        "to_state": next_state,
                        "condition_met": True,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    current_state = next_state
                    transitions_evaluated += 1
                else:
                    # No valid transition found - workflow ends
                    execution_log.append({
                        "phase": "transition",
                        "from_state": current_state,
                        "to_state": None,
                        "condition_met": False,
                        "message": "No matching transition condition",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    current_state = None
        
        # POST-EXECUTION VALIDATION: Check return value environment variables
        if workflow_def.get("return_values"):
            return_validation = await validate_environment_variables(
                session_id,
                workflow_def["return_values"],
                app_ctx,
                "return_values"
            )
            execution_log.append({
                "phase": "post_execution_validation",
                "validation_result": return_validation,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            if not return_validation["valid"]:
                return {
                    "success": False,
                    "final_state": "return_validation_failed",
                    "states_executed": states_executed,
                    "execution_log": execution_log,
                    "error": f"Workflow failed to set required return values: {', '.join(return_validation['missing_vars'])}. Expected variables: {', '.join(workflow_def['return_values'].keys())}"
                }
        
        return {
            "success": True,
            "final_state": "completed",
            "states_executed": states_executed,
            "execution_log": execution_log
        }
        
    except Exception as e:
        execution_log.append({
            "phase": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": False,
            "final_state": "error",
            "states_executed": states_executed if 'states_executed' in locals() else 0,
            "execution_log": execution_log,
            "error": str(e)
        }

async def _call_mcp_tool(
    tool_name: str, 
    params: Dict[str, Any], 
    session_id: str,
    app_ctx: "AppContext"
):
    """Call existing MCP tool with session context"""
    
    from .main import (
        send_input, get_screen_content, open_terminal,
        await_output, list_terminal_sessions, exit_terminal
    )
    from .models import (
        SendInputRequest, GetScreenContentRequest, OpenTerminalRequest,
        AwaitOutputRequest, DestroySessionRequest
    )
    from types import SimpleNamespace
    
    mock_ctx = SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=app_ctx)
    )
    
    # Auto-inject session_id if not provided
    if "session_id" not in params:
        params["session_id"] = session_id
    
    # Call appropriate MCP tool
    if tool_name == "send_input":
        request = SendInputRequest(**params)
        return await send_input(request, mock_ctx)
    elif tool_name == "get_screen_content":
        request = GetScreenContentRequest(**params)
        return await get_screen_content(request, mock_ctx)
    elif tool_name == "open_terminal":
        request = OpenTerminalRequest(**params)
        return await open_terminal(request, mock_ctx)
    elif tool_name == "await_output":
        request = AwaitOutputRequest(**params)
        return await await_output(request, mock_ctx)
    elif tool_name == "list_terminal_sessions":
        return await list_terminal_sessions(mock_ctx)
    elif tool_name == "exit_terminal":
        request = DestroySessionRequest(**params)
        return await exit_terminal(request, mock_ctx)
    else:
        raise ValueError(f"Unknown tool: {tool_name}. Available: send_input, get_screen_content, open_terminal, await_output, list_terminal_sessions, exit_terminal")

def _serialize_result(result: Any) -> Dict[str, Any]:
    """Serialize tool result for logging"""
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    elif hasattr(result, '__dict__'):
        return {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
    else:
        return {"value": str(result)}
```

### Step 5: MCP Tools with Environment Variable Contract Enforcement
**File**: `src/terminal_control_mcp/models.py` (append these new models)

```python
# Workflow MCP Tool Models
class CreateWorkflowRequest(BaseModel):
    """Request to create and validate a workflow with environment variable contracts"""
    workflow_definition: Dict[str, Any] = Field(..., description="Complete workflow definition with arguments and return_values")
    overwrite_existing: bool = Field(default=False, description="Whether to overwrite existing workflow with same name")

class CreateWorkflowResponse(BaseModel):
    """Response from workflow creation with contract information"""
    success: bool
    workflow_name: str
    stored_file: str
    workflow_signature: Dict[str, Any] = Field(description="Environment variable contract: arguments and return_values")
    validation_errors: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class RunWorkflowRequest(BaseModel):
    """Request to execute a workflow with environment variable validation"""
    workflow_name: str = Field(..., description="Name of workflow file (without .json extension)")
    session_id: str = Field(..., description="Terminal session ID to run workflow in")

class RunWorkflowResponse(BaseModel):
    """Response from workflow execution with validation results"""
    success: bool
    workflow_name: str
    session_id: str = Field(description="Terminal session ID workflow ran in")
    final_state: str
    states_executed: int
    workflow_signature: Dict[str, Any] = Field(description="Environment variable contract for reference")
    execution_log: List[Dict[str, Any]] = Field(description="Detailed execution log including validation phases")
    error: Optional[str] = None
```

**File**: `src/terminal_control_mcp/main.py` (add these imports and tools)

```python
# Add these imports
from .workflow_models import WorkflowDefinition
from .workflow_storage import WorkflowStorage
from .workflow_execution import execute_workflow
from .models import CreateWorkflowRequest, CreateWorkflowResponse, RunWorkflowRequest, RunWorkflowResponse

# Add these tools
@mcp.tool()
async def create_workflow(
    request: CreateWorkflowRequest, ctx: Context
) -> CreateWorkflowResponse:
    """Create and validate a workflow definition with state machine logic
    
    Creates state machine workflows with environment variable contracts and conditional transitions.
    
    WORKFLOW DEFINITION JSON SCHEMA (auto-generated from MCP tools):
    
    {
      "name": "workflow_identifier",  // lowercase, underscores only
      "description": "Human readable description",
      "arguments": {  // Required input environment variables
        "ENV_VAR_NAME": {
          "name": "ENV_VAR_NAME",
          "description": "Variable description", 
          "required": true
        }
      },
      "return_values": {  // Environment variables workflow must set
        "RESULT_VAR": {
          "name": "RESULT_VAR",
          "description": "Result description",
          "required": true  
        }
      },
      "initial_state": "start",
      "states": {
        "start": {
          "action": {
            "tool": "send_input",  // Available: open_terminal, send_input, get_screen_content, await_output, list_terminal_sessions, exit_terminal
            "params": {"input_text": "command\n"}  // Tool parameters (session_id auto-injected)
          },
          "transitions": [  // Conditional state machine transitions
            {
              "condition": "success",  // success, failure, timeout, pattern_match, pattern_no_match
              "next_state": "check_result"
            },
            {
              "condition": "failure", 
              "next_state": "handle_error"
            }
          ],
          "timeout_seconds": 30.0  // Optional state timeout
        },
        "check_result": {
          "action": {
            "tool": "await_output",
            "params": {"pattern": "Build complete", "timeout": 10.0}
          },
          "transitions": [
            {"condition": "pattern_match", "next_state": "success", "pattern": "SUCCESS"},
            {"condition": "timeout", "next_state": "failure"}
          ]
        },
        "success": {
          "action": {
            "tool": "send_input",
            "params": {"input_text": "export RESULT_VAR=SUCCESS\n"}
          },
          "transitions": []  // Terminal state
        }
      }
    }
    
    ENVIRONMENT VARIABLE CONTRACTS:
    - arguments: Variables that MUST exist before workflow runs (export VAR=value)
    - return_values: Variables workflow MUST set during execution  
    - Both validated automatically with clear error messages
    
    STATE MACHINE EXECUTION:
    - Conditional transitions based on MCP tool results
    - success/failure: Based on tool's success field
    - timeout: For await_output when pattern not found
    - pattern_match/pattern_no_match: Regex against screen content
    - Workflows continue until no valid transition found
    """
    
    try:
        from .workflow_schema import generate_workflow_json_schema, get_workflow_schema_documentation
        import jsonschema
        
        storage = WorkflowStorage()
        
        # Generate and validate against current JSON schema
        try:
            schema = generate_workflow_json_schema()  # Auto-generated from current MCP tools
            jsonschema.validate(request.workflow_definition, schema)
        except jsonschema.ValidationError as e:
            return CreateWorkflowResponse(
                success=False,
                workflow_name="",
                stored_file="",
                workflow_signature={},
                validation_errors=[f"JSON Schema validation failed: {e.message} at path: {'.'.join(str(p) for p in e.absolute_path)}"],
                error=f"Workflow definition does not match current MCP tool schema."
            )
        
        # Implementation continues...
        # (rest of create_workflow implementation)
        
    return create_workflow

# Generate the tool with current schema embedded in docstring
create_workflow = _generate_create_workflow_tool()
        
        # Validate with Pydantic model
        try:
            workflow = WorkflowDefinition(**request.workflow_definition)
        except Exception as e:
            return CreateWorkflowResponse(
                success=False,
                workflow_name="",
                stored_file="",
                workflow_signature={},
                validation_errors=[str(e)],
                error=f"Workflow model validation failed: {e}"
            )
        
        # Check for name conflicts
        existing_info = storage.get_workflow_info(workflow.name)
        if existing_info and not request.overwrite_existing:
            return CreateWorkflowResponse(
                success=False,
                workflow_name=workflow.name,
                stored_file="", 
                workflow_signature={},
                validation_errors=[f"Workflow '{workflow.name}' already exists"],
                error=f"Workflow '{workflow.name}' already exists. Use overwrite_existing=true to replace."
            )
        
        # Store workflow
        stored_name = storage.store_workflow(workflow.model_dump())
        
        # Create signature for agent
        signature = {
            "arguments": workflow.arguments,
            "return_values": workflow.return_values,
            "description": workflow.description
        }
        
        return CreateWorkflowResponse(
            success=True,
            workflow_name=stored_name,
            stored_file=f"{stored_name}.json",
            workflow_signature=signature
        )
                
    except Exception as e:
        return CreateWorkflowResponse(
            success=False,
            workflow_name="",
            stored_file="",
            workflow_signature={},
            validation_errors=[str(e)],
            error=f"Workflow creation failed: {e}"
        )

@mcp.tool()
async def run_workflow(
    request: RunWorkflowRequest, ctx: Context  
) -> RunWorkflowResponse:
    """Execute a stored workflow with strict environment variable validation
    
    VALIDATION PHASES:
    1. PRE-EXECUTION: Validates all required argument environment variables exist
       - Fails immediately if any required arguments missing
       - Agent must export variables before calling: export ARG_NAME=value
    
    2. EXECUTION: Runs workflow states by calling existing MCP tools
       - Uses specified terminal session for all operations
       - Logs all tool calls and results for debugging
    
    3. POST-EXECUTION: Validates all return value environment variables were set
       - Fails if workflow didn't set expected return values
       - Agent can read values after success: echo $RETURN_VAR
    
    CONTRACT ENFORCEMENT:
    - Required arguments MUST be set before execution starts
    - Expected return values MUST be set when execution completes
    - Clear error messages indicate which variables are missing
    """
    
    app_ctx = ctx.request_context.lifespan_context
    storage = WorkflowStorage()
    
    try:
        # Load and validate workflow exists
        workflow_def = storage.load_workflow(request.workflow_name)
        if not workflow_def:
            available = [wf["name"] for wf in storage.list_workflows()]
            return RunWorkflowResponse(
                success=False,
                workflow_name=request.workflow_name,
                session_id=request.session_id,
                final_state="workflow_not_found", 
                states_executed=0,
                workflow_signature={},
                execution_log=[],
                error=f"Workflow '{request.workflow_name}' not found. Available workflows: {', '.join(available)}"
            )
        
        # Validate workflow definition structure
        try:
            validated_workflow = WorkflowDefinition(**workflow_def)
        except Exception as e:
            return RunWorkflowResponse(
                success=False,
                workflow_name=request.workflow_name,
                session_id=request.session_id,
                final_state="definition_invalid",
                states_executed=0,
                workflow_signature={},
                execution_log=[],
                error=f"Workflow definition validation failed: {str(e)}"
            )
        
        # Execute workflow with full validation
        execution_result = await execute_workflow(
            workflow_def, 
            request.session_id, 
            app_ctx
        )
        
        # Update run statistics only on successful execution
        if execution_result["success"]:
            storage.update_run_stats(request.workflow_name)
        
        # Create environment variable contract signature
        signature = {
            "arguments": {name: var.model_dump() for name, var in validated_workflow.arguments.items()},
            "return_values": {name: var.model_dump() for name, var in validated_workflow.return_values.items()},
            "description": validated_workflow.description
        }
        
        return RunWorkflowResponse(
            success=execution_result["success"],
            workflow_name=request.workflow_name,
            session_id=request.session_id,
            final_state=execution_result["final_state"],
            states_executed=execution_result["states_executed"],
            workflow_signature=signature,
            execution_log=execution_result["execution_log"],
            error=execution_result.get("error")
        )
        
    except Exception as e:
        return RunWorkflowResponse(
            success=False,
            workflow_name=request.workflow_name,
            session_id=request.session_id,
            final_state="execution_error",
            states_executed=0,
            workflow_signature={},
            execution_log=[{
                "phase": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }],
            error=f"Workflow execution failed: {str(e)}"
        )
```

Update the main docstring:
```python
"""
Terminal Control MCP Server - FastMCP Implementation with Validated Workflow Automation
Provides interactive terminal session management and contract-enforced workflow automation for LLM agents

Core terminal tools:
- `open_terminal`: Open new terminal sessions with specified shell
- `get_screen_content`: Get current terminal output from sessions  
- `send_input`: Send input to interactive sessions (supports key combinations)
- `await_output`: Wait for specific regex patterns to appear in terminal output
- `list_terminal_sessions`: Show active sessions
- `exit_terminal`: Clean up sessions

Workflow automation tools:
- `create_workflow`: Create and validate workflow definitions with environment variable contracts
- `run_workflow`: Execute workflows with strict argument/return value validation

Workflow System Features:
- Environment variable contracts: Define required arguments and expected return values
- Fail-fast validation: Workflows fail immediately if required env vars missing
- Post-execution validation: Ensures workflows set all expected return values
- Agent-controlled: Agents manage env vars via terminal commands (export/echo)
- Terminal integration: Workflows execute within existing terminal sessions
"""
```

## Architecture Benefits

### Environment Variable Contract System
1. **Pre-execution Validation**: System validates required argument env vars exist before workflow starts
2. **Post-execution Validation**: System validates expected return value env vars were set after workflow completes  
3. **Agent Environment Control**: Agents set arguments via `export` and read results via `echo`
4. **Fail-fast Design**: Workflows fail immediately with clear error messages if contracts aren't met

### Seamless Architecture Integration  
1. **FastMCP Pattern**: Follows existing `@mcp.tool()` decorator pattern
2. **Pydantic Models**: Uses consistent Request/Response model architecture
3. **Existing Tool Integration**: Workflows call existing MCP tools like `send_input`, `get_screen_content`
4. **Session Reuse**: Workflows run in agent-specified terminal sessions

### Contract-Enforced Implementation  
1. **Storage with Validation**: System stores workflows with validated environment variable contracts
2. **Agent-Controlled Variables**: Agents manage env vars via terminal commands (export/echo)
3. **Boundary Validation**: Python validates env var contracts at workflow entry/exit points
4. **Clear Error Messages**: Specific guidance when required variables are missing or not set

This architecture provides agent autonomy while enforcing workflow contracts for reliable automation.

## Alternative Implementation (Fallback Option)

If dynamic docstring generation encounters issues, implement **Option 3: Schema as Separate Tool**:

### Additional Tool Required:
```python
@mcp.tool()
async def get_workflow_schema() -> Dict[str, Any]:
    """Get current workflow JSON schema (auto-generated from MCP tools)"""
    return {
        "json_schema": generate_workflow_json_schema(),
        "documentation": get_workflow_schema_documentation(), 
        "available_tools": list(introspect_mcp_tools().keys()),
        "schema_version": datetime.now(timezone.utc).isoformat()
    }
```

### Required Docstring Change:
The `create_workflow` docstring must include this disclaimer:
```
⚠️ IMPORTANT: Run get_workflow_schema() tool FIRST to get the current 
JSON schema before creating workflows. The schema is auto-generated from 
current MCP tools and may change when tools are updated.
```

**Agent Workflow**: `get_workflow_schema()` → `create_workflow()`

This fallback ensures schema introspection works even if f-string docstring generation fails.