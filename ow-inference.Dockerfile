FROM vllm/vllm-openai:latest

# Install SSH
RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd

# Create a directory for SSH keys
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# Update SSH configuration
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config && \
    echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config

COPY README.md .
COPY pyproject.toml .
COPY openweights openweights
COPY entrypoint.sh .
RUN python3 -m pip install .

# Create a symbolic link from python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

EXPOSE 22
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]