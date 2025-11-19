## Steps to configure Openshift Container Platform


🚀 Prerequisites

- Access to Openshift Contatiner platform on RHDP or you can use any On-Premise Openshift Cluster

- Slack token (for sending notifications via Slack)

- Model-as-a-Service account


### 📦 Step 1: Order RHDP Catalog Item if you don't have a cluster

- Order order this catalog item [RHDP](https://catalog.demo.redhat.com/catalog?search=rhoai&item=babylon-catalog-prod%2Fsandboxes-gpte.ocp4-demo-rhods-nvidia-gpu-aws.prod)
with default values

- Once the catalog item is ready, head over to the lab environment.

---

### 🔑 Step 2: Login to OCP and get CLI Token

- You need to obtain your CLI login token from the OpenShift Web Console.

    1. **Log in to the OpenShift Web Console** using your username and password.
    2. Click on your **username** located in the top-right corner.
    3. Select **"Copy Login Command"** from the dropdown menu.
    4. A dialog box will appear with the `oc login` command, which includes your token. It will look like this:

        ```bash
        oc login https://<openshift-api-server>:6443 --token=<your-token>
        ```
    
    6. Copy only the `--token=<your-token>` part. This is your CLI token.

### 🔑 Step 3: Deploy LLamaStack and AAP MCP

- You will now create a new OpenShift project and deploy the required components.

    1. Create the `llama-serve` Project

        In your terminal, run the following command to create a new project:

            oc new-project llama-serve
        
    2. Deploy AAP MCP server
       
          - Navigate to the `openshift` directory where your deployment files are located.

          - Deploy the AAP MCP server using the `oc apply` command:

                oc apply -k aap-mcp
    
          - After the deployment, you must update the `aap-mcp-secrets.yaml` file with your specific tokens.

               - In the **OpenShift Web Console**, go to the `llama-serve` project.
               - Find and select the **Secret** named `aap-mcp-secrets`.
               - Obtain your Ansible Automation Platform (AAP) token by following the instructions at the provided [URL](../AAP/STEPS_AAP_API_TOKEN.md
).
               - Update the following fields in the `aap-mcp-secrets` Secret with your information:
                 
                 -   `AAP_URL: https://<your-aap-server>/api/controller/v2`
                 -   `AAP_TOKEN`
                 -   `EDA_URL: https://<your-aap-server>/api/eda/v1`
                 -   `EDA_TOKEN`


    3. Deploy LLamaStack 

    
         1.  **Verify Pod Status**: Before you begin, ensure that the `aap-mcp` pod is up and in a `Running` state.
      
         2. **Deploy LLamaStack**:
            
            -   Navigate to the `openshift` directory in your terminal.
            -   Run the following command to deploy the LLamaStack:
        
                ```bash
                oc apply -k llama-stack
                ```
            
         3.  **Update Secrets**: After deployment, you need to configure the `llama-secrets` file.
            
                -   In the OpenShift Web Console, navigate to the `llama-serve` project.
                -   Go to the **Secrets** section and select `llama-secret`.
                -   Obtain a token from your MaaS (Model as a Service) by visiting the provided URL.
                -   Update the token for the `llama-3b` model within the `llama-secret` file.
           
    4. Deploy Streamlit (LLamaStack UI)

    
         1.  **Verify Pod Status**: Before you begin, ensure that the `llamastack-deployment` pod is up and in a `Running` state.
      
         2. **Deploy Streamlit**:
            
            -   Navigate to the `openshift` directory in your terminal.
            -   Run the following command to deploy the LLamaStack:
        
                ```bash
                oc apply -k streamlit
                ```
            
         3.  **Update Tavily Secret**(Optional): After deployment, if you want to use Tavily, configure the `tavily_secret` secret.
            
                -   In the OpenShift Web Console, navigate to the `llama-serve` project.
                -   Go to the **Secrets** section and select `tavily_secret`.
                -   Obtain a token from Tavily.
                -   Update the token for the `tavily-search-api-key` key in the `tavily_secret` secret.
        
         4.  **Verify Deployment**:
            -   Confirm that the Streamlit pod is now up and running correctly.


**Once the Streamlit pod is running, return to the [Trigger the workflow](../Readme.md#-prerequisites) section for details on the next steps.**
