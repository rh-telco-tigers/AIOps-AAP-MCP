import os
import httpx
import urllib3
from mcp.server.fastmcp import FastMCP
from typing import Any
import uvicorn
import sys
import re
import json
import yaml 

# Disable SSL warnings for lab environments with self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Environment variables for authentication
AAP_URL = os.getenv("AAP_URL")
AAP_TOKEN = os.getenv("AAP_TOKEN")

EDA_URL = os.getenv("EDA_URL")
EDA_TOKEN = os.getenv("EDA_TOKEN")


if not AAP_TOKEN:
    raise ValueError("AAP_TOKEN is required")

# Headers for API authentication
HEADERS = {"Authorization": f"Bearer {AAP_TOKEN}", "Content-Type": "application/json"}
HEADERS_EDA = {"Authorization": f"Bearer {EDA_TOKEN}", "Content-Type": "application/json"}


# Initialize FastMCP
mcp = FastMCP("ansible", host="0.0.0.0", port=8000)


async def make_request(url: str, method: str = "GET", json: dict = None) -> Any:
    """Helper function to make authenticated API requests to AAP."""
    # For lab environments, disable SSL verification for self-signed certificates
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.request(method, url, headers=HEADERS, json=json)
    if response.status_code not in [200, 201]:
        return f"Error {response.status_code}: {response.text}"
    return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text

async def make_request_eda(url: str, method: str = "GET", json: dict = None) -> Any:
    """Helper function to make authenticated API requests to EDA."""
    # For lab environments, disable SSL verification for self-signed certificates
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.request(method, url, headers=HEADERS_EDA, json=json)
    if response.status_code not in [200, 201]:
        return f"Error {response.status_code}: {response.text}"
    return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text


@mcp.tool()
async def get_recent_prompt_job_id() -> Any:
    """Return the most recent job id for the Lightspeed Prompt job template."""
    job_data = await make_request(
        f"{AAP_URL}/jobs/?name=Get%20Lightspeed%20Prompt&order_by=-id"
    )

    if not job_data or "results" not in job_data or len(job_data["results"]) == 0:
        raise ValueError("Could not retrieve recent Lightspeed Prompt job ID")

    return job_data["results"][0]["id"]

@mcp.tool()
async def get_job_template_id(name: str) -> Any:
    """Return the Template ID for a given job template name."""
    job_data = await make_request(
        f"{AAP_URL}/job_templates/?name={name}"
    )

    if not job_data or "results" not in job_data or len(job_data["results"]) == 0:
        raise ValueError(f"Could not retrieve job template ID for '{name}'")

    return job_data["results"][0]["id"]



@mcp.tool()
async def run_workflow(extra_vars: dict = {}) -> Any:
    """Run Remediation Workflow with extra_vars."""

    try:
        # Step 1: Get Remediation Workflow template ID
        job_data = await make_request(
            f"{AAP_URL}/workflow_job_templates/?name=Remediation%20Workflow"
        )

        if not job_data or "results" not in job_data or len(job_data["results"]) == 0:
            raise ValueError("Could not retrieve Remediation Workflow template ID")

        template_id = job_data["results"][0]["id"]

        # Step 2: Launch the workflow
        response = await make_request(
            f"{AAP_URL}/workflow_job_templates/{template_id}/launch/",
            method="POST",
            json={"extra_vars": extra_vars}
        )

        return response

    except Exception as e:
        return f"Error: Could not run Remediation Workflow: {e}"
    


@mcp.tool()
async def run_lightspeed_job_and_get_yaml(template_id: int, extra_vars: dict = {}) -> str:
    """
    Run the Lightspeed job template by ID, wait for it to finish, and then give the generated Playbook 
    from the job stdout output (full debug logic included).
    """
    # Step 1: Launch the job
    launch_response = await make_request(
        f"{AAP_URL}/job_templates/{template_id}/launch/",
        method="POST",
        json={"extra_vars": extra_vars}
    )

    job_id = launch_response.get("id")
    if not job_id:
        return f"Error: Could not launch job. Response: {launch_response}"

    # Step 2: Wait for job completion
    import asyncio
    while True:
        job_status = await make_request(f"{AAP_URL}/jobs/{job_id}/")
        if job_status.get("status") in ["successful", "failed", "error", "canceled"]:
            break
        await asyncio.sleep(2)

    # Step 3: Retrieve job stdout
    stdout = await make_request(f"{AAP_URL}/jobs/{job_id}/stdout/?format=txt")
    if isinstance(stdout, str) and "Error" in stdout:
        return stdout

    # Step 4: Full debug YAML extraction (from your original function)
    import re
    debug_info = f"DEBUG: First 1000 chars of stdout:\n{stdout[:1000]}\n\n"
    yaml_pattern = r'Display Ansible Playbook in YAML.*?ok: \[localhost\] => \{\s*"msg":\s*"([^"]*)"\s*\}'
    debug_info += f"DEBUG: Looking for pattern: {yaml_pattern}\n"
    match = re.search(yaml_pattern, stdout, re.DOTALL)

    if not match:
        # Try alternative patterns
        debug_info += "DEBUG: Primary pattern not found, trying alternatives...\n"
        
        # Alternative 1
        alt_pattern1 = r'Display Ansible Playbook in YAML.*?ok: \[localhost\] => \{\s*"msg":\s*"([^"]*)"\s*\}'
        match = re.search(alt_pattern1, stdout, re.DOTALL)
        
        if not match:
            # Alternative 2
            alt_pattern2 = r'"msg":\s*"([^"]*)"'
            all_matches = re.findall(alt_pattern2, stdout)
            debug_info += f"DEBUG: Found {len(all_matches)} msg fields:\n"
            for i, msg in enumerate(all_matches[:5]):  # First 5 msgs
                debug_info += f"  {i}: {msg[:100]}...\n"
            
            # Look for YAML content
            for msg in all_matches:
                if msg.startswith('---') or 'ansible.builtin.debug' in msg or 'hosts:' in msg:
                    debug_info += f"DEBUG: Found potential YAML in msg: {msg[:200]}...\n"
                    escaped_yaml = msg
                    break
            else:
                return debug_info + "Error: Could not find 'Display Ansible Playbook in YAML' section in job output"
        else:
            escaped_yaml = match.group(1)
         
    else:
        escaped_yaml = match.group(1)
        debug_info += "DEBUG: Found match with primary pattern\n"

    # Step 5: Clean YAML
    #cleaned_yaml = escaped_yaml.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    cleaned_yaml = escaped_yaml.replace('\\n', '\n')
    if cleaned_yaml.startswith('"') and cleaned_yaml.endswith('"'):
        cleaned_yaml = cleaned_yaml[1:-1]
    
    debug_info += f"DEBUG: Final cleaned YAML:\n{cleaned_yaml}\n"
    return debug_info + f"SUCCESS (Job ID {job_id}): {cleaned_yaml}"


@mcp.tool()
async def get_llm_response() -> str:
    """Give a LLM prompt for solving the event triggerred
    
    This function retrieves the stdout from an Ansible job and parses it to find
    the 'TASK [Show the LLM response text]' section, extracting the 'msg' value.
    """

    try:
        job_id = await get_recent_prompt_job_id()
    except Exception as e:
        return f"Error: {e}"


    # Get the job stdout
    stdout = await make_request(f"{AAP_URL}/jobs/{job_id}/stdout/?format=txt")

    if isinstance(stdout, str) and "Error" in stdout:
        return stdout

    # Debug: return first few chars of stdout
    debug_info = f"DEBUG: First 500 chars of stdout:\n{stdout[:500]}\n\n"

    # Regex pattern to capture msg under the LLM response task
    llm_pattern = r'TASK \[Show the LLM response text\].*?ok: \[localhost\] => \{\s*"msg":\s*"([^"]+)"\s*\}'
    match = re.search(llm_pattern, stdout, re.DOTALL)

    if not match:
        # fallback: grab any "msg" fields if task-specific search fails
        debug_info += "DEBUG: Primary pattern not found, looking for any msg fields...\n"
        alt_pattern = r'"msg":\s*"([^"]+)"'
        msgs = re.findall(alt_pattern, stdout)

        if not msgs:
            return debug_info + "Error: Could not find any LLM response text in job output"
        
        # pick the last one (likely the LLM response)
        response = msgs[-1]
        debug_info += f"DEBUG: Using fallback msg field: {response[:200]}...\n"
    else:
        response = match.group(1)
        debug_info += "DEBUG: Found match in primary pattern\n"

    

    return f"SUCCESS: LLM Response: {response}"

    
@mcp.tool()
async def list_events() -> Any:
    """List the most recent Event."""
    return await make_request_eda(f"{EDA_URL}/audit-rules/")



@mcp.tool()
async def list_inventories() -> Any:
    """List all inventories in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventories/")


@mcp.tool()
async def get_inventory(inventory_id: str) -> Any:
    """Get details of a specific inventory by ID."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/")


##@mcp.tool()
##async def run_job(name: str, extra_vars: dict = {}) -> Any:
##    """Run a job template by name, optionally with extra_vars."""
##    try:
##        template_id = await get_job_template_id(name)
##    except Exception as e:
##        return f"Error: Could not get Template ID: {e}"

##    return await make_request(
##        f"{AAP_URL}/job_templates/{template_id}/launch/", method="POST", json={"extra_vars": extra_vars}
##    )

@mcp.tool()
async def run_job(name: str) -> Any:
    """Run a job template by name, optionally with extra_vars."""
    try:
        template_id = await get_job_template_id(name)
    except Exception as e:
        return f"Error: Could not get Template ID: {e}"

    return await make_request(
        f"{AAP_URL}/job_templates/{template_id}/launch/", method="POST")


@mcp.tool()
async def job_status(job_id: int) -> Any:
    """Check the status of a job by ID."""
    return await make_request(f"{AAP_URL}/jobs/{job_id}/")



@mcp.tool()
async def job_logs(job_id: int) -> str:
    """Retrieve logs for a job."""
    return await make_request(f"{AAP_URL}/jobs/{job_id}/stdout/?format=txt")





@mcp.tool()
async def create_project(
    name: str,
    organization_id: int,
    source_control_url: str,
    source_control_type: str = "git",
    description: str = "",
    execution_environment_id: int = None,
    content_signature_validation_credential_id: int = None,
    source_control_branch: str = "",
    source_control_refspec: str = "",
    source_control_credential_id: int = None,
    clean: bool = False,
    update_revision_on_launch: bool = False,
    delete: bool = False,
    allow_branch_override: bool = False,
    track_submodules: bool = False,
) -> Any:
    """Create a new project in Ansible Automation Platform."""

    payload = {
        "name": name,
        "description": description,
        "organization": organization_id,
        "scm_type": source_control_type.lower(),  # Git is default
        "scm_url": source_control_url,
        "scm_branch": source_control_branch,
        "scm_refspec": source_control_refspec,
        "scm_clean": clean,
        "scm_delete_on_update": delete,
        "scm_update_on_launch": update_revision_on_launch,
        "allow_override": allow_branch_override,
        "scm_track_submodules": track_submodules,
    }

    if execution_environment_id:
        payload["execution_environment"] = execution_environment_id
    if content_signature_validation_credential_id:
        payload["signature_validation_credential"] = content_signature_validation_credential_id
    if source_control_credential_id:
        payload["credential"] = source_control_credential_id

    return await make_request(f"{AAP_URL}/projects/", method="POST", json=payload)


@mcp.tool()
async def create_job_template(
    name: str,
    project_id: int,
    playbook: str,
    inventory_id: int,
    job_type: str = "run",
    description: str = "",
    #credential_id: int = None,
    #execution_environment_id: int = None,
    #labels: list[str] = None,
    #forks: int = 0,
    limit: str = "",
    #verbosity: int = 0,
    #timeout: int = 0,
    #job_tags: list[str] = None,
    #skip_tags: list[str] = None,
    extra_vars: dict = None,
    #privilege_escalation: bool = False,
    #concurrent_jobs: bool = False,
    #provisioning_callback: bool = False,
    #enable_webhook: bool = False,
    #prevent_instance_group_fallback: bool = False,
) -> Any:
    """Create a new job template in Ansible Automation Platform."""
    
    
    job_type = job_type if job_type is not None else "run"
    #description = description if description is not None else ""
    #limit = limit if limit is not None else ""
    
    #forks = forks if forks is not None else 0
    #verbosity = verbosity if verbosity is not None else 0
    #timeout = timeout if timeout is not None else 0

    #privilege_escalation = privilege_escalation if privilege_escalation is not None else False
    #concurrent_jobs = concurrent_jobs if concurrent_jobs is not None else False
    #provisioning_callback = provisioning_callback if provisioning_callback is not None else False
    #enable_webhook = enable_webhook if enable_webhook is not None else False
    #prevent_instance_group_fallback = prevent_instance_group_fallback if prevent_instance_group_fallback is not None else False


    payload = {
        "name": name,
        "description": description,
        "job_type": job_type,
        "project": project_id,
        "playbook": playbook,
        "inventory": inventory_id,
        #"forks": forks,
        #"limit": limit,
        #"verbosity": verbosity,
        #"timeout": timeout,
        #"ask_variables_on_launch": bool(extra_vars),
        #"ask_tags_on_launch": bool(job_tags),
        #"ask_skip_tags_on_launch": bool(skip_tags),
        #"ask_credential_on_launch": credential_id is None,
        #"ask_execution_environment_on_launch": execution_environment_id is None,
        #"ask_labels_on_launch": labels is None,
        #"ask_inventory_on_launch": False,  # Inventory is required, so not prompting
        #"ask_job_type_on_launch": False,  # Job type is required, so not prompting
        #"become_enabled": privilege_escalation,
        #"allow_simultaneous": concurrent_jobs,
        #"scm_branch": "",
        #"webhook_service": "github" if enable_webhook else "",
        #"prevent_instance_group_fallback": prevent_instance_group_fallback,
    }

    #if credential_id:
    #    payload["credential"] = credential_id
    #if execution_environment_id:
    #    payload["execution_environment"] = execution_environment_id
    #if labels:
    #    payload["labels"] = labels
    #if job_tags:
    #    payload["job_tags"] = job_tags
    #if skip_tags:
    #    payload["skip_tags"] = skip_tags
    if extra_vars:
        payload["extra_vars"] = extra_vars

    return await make_request(f"{AAP_URL}/job_templates/", method="POST", json=payload)


@mcp.tool()
async def list_inventory_sources() -> Any:
    """List all inventory sources in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventory_sources/")


@mcp.tool()
async def get_inventory_source(inventory_source_id: int) -> Any:
    """Get details of a specific inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/")


@mcp.tool()
async def create_inventory_source(
    name: str,
    inventory_id: int,
    source: str,
    credential_id: int,
    source_vars: dict = None,
    update_on_launch: bool = True,
    timeout: int = 0,
) -> Any:
    """Create a dynamic inventory source. Claude will ask for the source type and credential before proceeding."""
    valid_sources = [
        "file",
        "constructed",
        "scm",
        "ec2",
        "gce",
        "azure_rm",
        "vmware",
        "satellite6",
        "openstack",
        "rhv",
        "controller",
        "insights",
        "terraform",
        "openshift_virtualization",
    ]

    if source not in valid_sources:
        return f"Error: Invalid source type '{source}'. Please select from: {', '.join(valid_sources)}"

    if not credential_id:
        return "Error: Credential is required to create an inventory source."

    payload = {
        "name": name,
        "inventory": inventory_id,
        "source": source,
        "credential": credential_id,
        "source_vars": source_vars,
        "update_on_launch": update_on_launch,
        "timeout": timeout,
    }
    return await make_request(f"{AAP_URL}/inventory_sources/", method="POST", json=payload)


@mcp.tool()
async def update_inventory_source(inventory_source_id: int, update_data: dict) -> Any:
    """Update an existing inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="PATCH", json=update_data)


@mcp.tool()
async def delete_inventory_source(inventory_source_id: int) -> Any:
    """Delete an inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="DELETE")


@mcp.tool()
async def sync_inventory_source(inventory_source_id: int) -> Any:
    """Manually trigger a sync for an inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/update/", method="POST")


@mcp.tool()
async def create_inventory(
    name: str,
    organization_id: int,
    description: str = "",
    kind: str = "",
    host_filter: str = "",
    variables: dict = None,
    prevent_instance_group_fallback: bool = False,
) -> Any:
    """Create an inventory in Ansible Automation Platform."""
    payload = {
        "name": name,
        "organization": organization_id,
        "description": description,
        "kind": kind,
        "host_filter": host_filter,
        "variables": variables,
        "prevent_instance_group_fallback": prevent_instance_group_fallback,
    }
    return await make_request(f"{AAP_URL}/inventories/", method="POST", json=payload)


@mcp.tool()
async def delete_inventory(inventory_id: int) -> Any:
    """Delete an inventory from Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/", method="DELETE")


#@mcp.tool()
#async def list_job_templates() -> Any:
    #"""List all unique job template names available in Ansible Automation Platform."""
    #response = await make_request(f"{AAP_URL}/job_templates/")

    # Extract and deduplicate names
   # job_templates = response.get("results", [])
  #  unique_names = sorted({template["name"] for template in job_templates if "name" in template})

 #   return unique_names

@mcp.tool()
async def list_job_templates() -> Any:
    """List all unique job template names with their descriptions from Ansible Automation Platform."""
    response = await make_request(f"{AAP_URL}/job_templates/")

    job_templates = response.get("results", [])
    
    # Extract name and description, deduplicate by name
    seen = set()
    templates_with_desc = []
    for template in job_templates:
        name = template.get("name")
        description = template.get("description", "")
        if name and name not in seen:
            templates_with_desc.append({"name": name, "description": description})
            seen.add(name)
    
    # Sort by name
    templates_with_desc.sort(key=lambda x: x["name"])
    return templates_with_desc


@mcp.tool()
async def get_job_template(template_id: int) -> Any:
    """Retrieve details of a specific job template."""
    return await make_request(f"{AAP_URL}/job_templates/{template_id}/")

@mcp.tool()
async def list_jobs() -> Any:
    """List all jobs available in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/jobs/")



@mcp.tool()
async def list_workflow_templates() -> Any:
    """List all workflow jobs available in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/")

@mcp.tool()
async def list_recent_jobs(hours: int = 24) -> Any:
    """List all jobs executed in the last specified hours (default 24 hours)."""
    from datetime import datetime, timedelta

    time_filter = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    return await make_request(f"{AAP_URL}/jobs/?created__gte={time_filter}")


# Host Management Tools
@mcp.tool()
async def list_hosts(inventory_id: int) -> Any:
    """List all hosts in a specific inventory."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/hosts/")


@mcp.tool()
async def get_host_details(host_id: int) -> Any:
    """Get detailed information about a specific host including facts and variables."""
    return await make_request(f"{AAP_URL}/hosts/{host_id}/")


@mcp.tool()
async def get_host_facts(host_id: int) -> Any:
    """Get gathered facts for a specific host."""
    return await make_request(f"{AAP_URL}/hosts/{host_id}/ansible_facts/")


@mcp.tool()
async def add_host_to_inventory(
    inventory_id: int, hostname: str, description: str = "", variables: dict = None, enabled: bool = True
) -> Any:
    """Add a new host to an inventory with optional variables."""
    payload = {
        "name": hostname,
        "description": description,
        "inventory": inventory_id,
        "enabled": enabled,
        "variables": variables or {},
    }
    return await make_request(f"{AAP_URL}/hosts/", method="POST", json=payload)


@mcp.tool()
async def update_host(host_id: int, update_data: dict) -> Any:
    """Update host settings including variables, description, or enabled status."""
    return await make_request(f"{AAP_URL}/hosts/{host_id}/", method="PATCH", json=update_data)


@mcp.tool()
async def delete_host(host_id: int) -> Any:
    """Delete a host from inventory."""
    return await make_request(f"{AAP_URL}/hosts/{host_id}/", method="DELETE")


@mcp.tool()
async def get_failed_hosts(inventory_id: int) -> Any:
    """Get list of hosts with active failures in an inventory."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/hosts/?has_active_failures=true")


@mcp.tool()
async def list_groups(inventory_id: int) -> Any:
    """List all groups in a specific inventory."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/groups/")


@mcp.tool()
async def get_group_details(group_id: int) -> Any:
    """Get detailed information about a specific group."""
    return await make_request(f"{AAP_URL}/groups/{group_id}/")


@mcp.tool()
async def create_group(inventory_id: int, name: str, description: str = "", variables: dict = None) -> Any:
    """Create a new group in an inventory."""
    payload = {"name": name, "description": description, "inventory": inventory_id, "variables": variables or {}}
    return await make_request(f"{AAP_URL}/groups/", method="POST", json=payload)


@mcp.tool()
async def add_host_to_group(group_id: int, host_id: int) -> Any:
    """Add a host to a group."""
    payload = {"id": host_id}
    return await make_request(f"{AAP_URL}/groups/{group_id}/hosts/", method="POST", json=payload)


@mcp.tool()
async def remove_host_from_group(group_id: int, host_id: int) -> Any:
    """Remove a host from a group."""
    return await make_request(
        f"{AAP_URL}/groups/{group_id}/hosts/", method="POST", json={"id": host_id, "disassociate": True}
    )


@mcp.tool()
async def get_host_groups(host_id: int) -> Any:
    """Get all groups that a host belongs to."""
    return await make_request(f"{AAP_URL}/hosts/{host_id}/groups/")


@mcp.tool()
async def run_adhoc_command(
    inventory_id: int,
    module_name: str,
    module_args: str = "",
    limit: str = "",
    credential_id: int = None,
    become_enabled: bool = False,
    verbosity: int = 0,
) -> Any:
    """Run an ad-hoc Ansible command against inventory hosts."""
    payload = {
        "inventory": inventory_id,
        "module_name": module_name,
        "module_args": module_args,
        "limit": limit,
        "become_enabled": become_enabled,
        "verbosity": verbosity,
    }
    if credential_id:
        payload["credential"] = credential_id

    return await make_request(f"{AAP_URL}/ad_hoc_commands/", method="POST", json=payload)


@mcp.tool()
async def get_adhoc_command_status(adhoc_id: int) -> Any:
    """Get status of an ad-hoc command."""
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{adhoc_id}/")


@mcp.tool()
async def get_adhoc_command_output(adhoc_id: int) -> Any:
    """Get output/logs from an ad-hoc command."""
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{adhoc_id}/stdout/?format=txt")


# Project Management Tools
@mcp.tool()
async def list_projects() -> Any:
    """List all projects in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/projects/")


@mcp.tool()
async def get_project(project_id: int) -> Any:
    """Get details of a specific project by ID."""
    return await make_request(f"{AAP_URL}/projects/{project_id}/")


@mcp.tool()
async def list_project_updates() -> Any:
    """List all project update jobs (SCM sync operations)."""
    return await make_request(f"{AAP_URL}/project_updates/")


@mcp.tool()
async def get_project_update(update_id: int) -> Any:
    """Get status and details of a specific project update job."""
    return await make_request(f"{AAP_URL}/project_updates/{update_id}/")


@mcp.tool()
async def get_project_update_logs(update_id: int) -> str:
    """Get logs from a project update job (SCM sync operation)."""
    return await make_request(f"{AAP_URL}/project_updates/{update_id}/stdout/?format=txt")


@mcp.tool()
async def update_project(project_id: int) -> Any:
    """Trigger a project update (SCM sync) for a specific project."""
    return await make_request(f"{AAP_URL}/projects/{project_id}/update/", method="POST")



if __name__ == "__main__":
   mcp.run(transport="sse")