# AIOps Automation Solution with Ansible Automation Platform & LlamaStack on OpenShift

## 📌 Overview
This project demonstrates an **end-to-end AIOps automation framework** built using:
- **Ansible Automation Platform (AAP)**
- **OpenShift AI**
- **LLamaStack Agent**
- **Ansible Lightspeed**

The solution automates detection, analysis, notification, and remediation of node/service failures (e.g., HTTP service downtime).

---

## ⚙️ Workflow


<img src="./images/Final-Architecture.png" alt="Architecture" height="400" />


This workflow demonstrates how Event-Driven Ansible (EDA), AI Insights, and Lightspeed integrate with Ansible Automation Platform (AAP) to detect, analyze, and remediate service outages using a combination of autonomous agents and human-in-the-loop automation.

---

### 🧭 Part 1: Error Detection

**1. Error/Event takes place**

An error or event occurs on a node, triggering the start of the incident lifecycle.

<img src="./images/architecture-1.png" alt="drawing" height= "250" />

**2. Alert & Trigger**

Kafka detects a service outage and publishes an alert.
Event-Driven Ansible (EDA) subscribes to this event and triggers the AI Insights Workflow in Ansible Automation Platform (AAP).

<img src="./images/architecture-2.png" alt="drawing" height= "250" />

**3. AI Analysis**

The **AI Insights Workflow** initiates the analysis phase:

- The error is sent to an Agent for Root Cause Analysis (RCA).

- Based on the RCA, a prompt is created to generate a remediation playbook.

- Simultaneously, the Network Operations Center (NOC) engineer is notified via Slack about the issue.

<img src="./images/architecture-3.png" alt="drawing" height= "250" />

### ⚙️ Part 2: Automated Remediation (Agent-driven)
**4. Agent Decision**

The Agent evaluates whether it has the capability to resolve the detected issue autonomously:

- If YES: It directly executes the appropriate automation template to remediate the issue.

   <img src="./images/architecture-4.png" alt="drawing" height= "250" />

- If NO: It escalates the case to the human-in-the-loop process for manual intervention.

   <img src="./images/architecture-5.png" alt="drawing" height= "250" />



### 🧑‍💻 Part 3: Human-in-the-loop Automation

**5. Playbook Generation using Ansible Lightspeed**

When manual intervention is required:

- The NOC engineer interacts with the Agent UI, where the AI Insights Workflow provides an auto-generated remediation prompt based on RCA. The engineer can review and customize this prompt before proceeding.
- Once finalized, the Agent communicates with the **AAP MCP (Model Context Protocol)**, which in turn triggers the **Lightspeed Generation Template** within Ansible Automation Platform (AAP) — configured with Ansible Lightspeed credentials.
- Lightspeed then uses the provided prompt to generate a remediation playbook, which is sent back to the Agent UI for the engineer to review and approve.


<img src="./images/architecture-6.png" alt="drawing" height= "250" />

**6. Playbook Approval & Execution**

- After reviewing and approving the generated playbook, the engineer instructs the Agent to initiate the Remediation Workflow.
- The Agent then triggers the workflow in Ansible Automation Platform (AAP), which automatically commits the playbook to Git and syncs the AAP project for deployment.

<img src="./images/architecture-7.png" alt="drawing" height= "250" />

**7. Remediation**

- Finally, the engineer instructs the Agent to execute the newly created Job Template.
- The Agent triggers the Job Template in Ansible Automation Platform (AAP), and restoring normal service operation.

<img src="./images/architecture-8.png" alt="drawing" height= "250" />

## Steps to Run the Workflow:

### ✅ Prerequisites

Before you begin, ensure you have the following configured:

- **LlamaStack** on OpenShift → [OpenShift setup steps](./openshift/README.md)  
- **Ansible Automation Platform (AAP)** → [AAP setup steps](./AAP/Readme.md)  

---
---

### 🚀 Steps to Run the Workflow

#### Step 1: Trigger the Workflow

1. **Run the Break Apache Job Template**  
   - Execute the job template ❌ **Break Apache**.  
   - This inserts an invalid directive into the Apache configuration and restarts the service, causing an intentional failure.


2. **Verify Event Pickup in Event-Driven Ansible (EDA)**  
   - Navigate to **Automation Decisions → Rulebook Activations**.  
   - Confirm that **EDA** has detected and picked up the event.


3. **Confirm Workflow Execution in AAP Controller**  
   - Go to **Automation Controller → Jobs**.  
   - Look for the workflow named **AI Insights and Lightspeed Prompt Generation**.  
   - ✅ A successful run will be marked **green**.


4. **Check for Auto-Generated Remediation Template**  
   - Navigate to **Templates** in AAP.  
   - You should now see a new job template:  
     - 🧠 **Lightspeed Remediation Playbook Generator**


5. **Review Slack Notifications**  
   - Open your Slack channel and review the automated notification.  
   - Key details included:  

     - 🛑 **HTTPD Error Logs**  
       Logs automatically collected from the webserver showing the failure.  

     - 🧠 **AI Insights (RCA)**  
       Red Hat AI parsed the logs and generated a **Root Cause Analysis (RCA)** explaining why the failure occurred.  


By following these steps, you will have:  
- Simulated an Apache service failure.  
- Verified that **EDA** captured the event.  
- Executed an **AI-assisted remediation workflow** in AAP.  
- Received **automated RCA insights** and a **generated remediation playbook template** via **Lightspeed**.  
- Notified your team with contextual insights directly in **Slack**.  

---

#### Step 2 - Remediation Workflow

1. **Login to OpenShift Container Platform**  
   Use your provided credentials to log in.

2. **Navigate to the LlamaStack UI**  
   - Go to **Networking → Routes**.  
   - Click on the route next to **Streamlit**. This opens the **LlamaStack UI**.

3. **Configure MCP Server**  
   - In the UI, select **Tools**.  
   - Choose **mcp:aap** under **MCP Servers**.  
   - Increase **Max Token** to at least **2000**.

4. **Interact with AAP MCP Server**  

   You can now issue prompts directly to the AAP MCP server.  

   Enter the following prompts in sequence:
   **Prompt 1** 
   ```text
   1. List the most recent Event.
   ```

   Expected Response

   <img src="./images/llamastack-ui-1.png" alt="Prompt Response"  width="500" />

   **Prompt 2**
   ```text
   2. "Return the LLM Prompt generated"
   ```
   
   Expected Response
   
   <img src="./images/llamastack-ui-2.png" alt="Prompt Response"  width="500" />


   > **Important:**  
   > Before proceeding to the next step, **refresh the UI**.  
   > This is required because the underlying LLM in **LlamaStack** may hallucinate if the context length is exceeded.

   **Prompt 3**
   ```text
      Run a Lightspeed job template with ID 19 with extra_vars
      {
      "lightspeed_prompt": "Remove the invalid directive 'InvalidDirectiveHere' from the httpd configuration file. Then restart the httpd service. Execute against node 1 host"
      }
      and then give the generated playbook
   ```

   
   The prompt is the same as in Response 2, but with "Execute against Node 1" added, since the HTTP service is down on Node 1 and the playbook should target it.


   **Prompt 4**
   ```text
   Run Remediation Workflow  Template  extra_vars is 
   
   { "lightspeed_playbook": <cleaned_yaml> }
   ```
      
   **Prompt 5**

   ```text
   Run a job template by name Execute HTTPD Remediation
   ```
