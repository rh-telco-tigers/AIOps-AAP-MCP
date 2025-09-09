# Use a Python base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install uv, the package manager
RUN pip install uv

# Copy all the project files and directories into the container.
COPY . .

# Use 'uv pip install' to install dependencies from pyproject.toml
# The --system flag ensures installation into the system's Python environment.
RUN uv pip install --system .

# Expose the port the server runs on
EXPOSE 8000

# Run the ansible.py script directly.
CMD ["python", "ansible.py"]