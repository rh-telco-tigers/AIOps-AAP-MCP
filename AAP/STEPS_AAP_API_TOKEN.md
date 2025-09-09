### Getting Your API Token for AAP

**Method 1: AAP Web Interface**

1. Log into your AAP web interface
2. Click on your username in the top right corner
3. Select "User Settings" or "My Profile"
4. Navigate to the "Tokens" section
5. Click "Add" or "Create Token"
6. Set the scope to "Write" for full functionality
7. Copy the generated token immediately (it won't be shown again)

--- 
**Method 2: Command Line**

        curl -k -X POST \
        "https://your-aap-server.com/api/v2/tokens/" \
        -H "Content-Type: application/json" \
        -u "username:password" \
        -d '{
            "description": "MCP Server Token",
            "application": null,
            "scope": "write"
        }'


Follow **Method 1** to create a new token for Event Driven Ansible
