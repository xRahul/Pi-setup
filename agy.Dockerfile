FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

# Minimal runtime essentials for terminal and git operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    tmux \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Generate UTF-8 locale for terminal box-drawing characters
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# Install verified static ttyd aarch64 binary (v1.7.7)
ADD https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.aarch64 /usr/local/bin/ttyd
RUN chmod +x /usr/local/bin/ttyd

# Copy customized index.html with Cascadia Mono web fonts and mobile-web-app-capable meta
COPY ttyd-index.html /usr/local/share/ttyd/index.html

# Configure tmux for low-latency escape handling and truecolor
RUN printf "%s\n" \
    "set -s escape-time 10" \
    "set -g mouse on" \
    "set -g default-terminal 'xterm-256color'" \
    "set -ga terminal-overrides ',xterm-256color:Tc'" \
    "set -g status-style 'bg=#1e1e2e,fg=#cdd6f4'" \
    "set -g history-limit 10000" \
    > /etc/tmux.conf

# Create session launcher script: launches or attaches to persistent bash shell
RUN printf "%s\n" \
    "#!/bin/bash" \
    "tmux has-session -t agy 2>/dev/null" \
    "if [ \$? != 0 ]; then" \
    "    tmux new-session -d -s agy -n 'terminal' bash" \
    "fi" \
    "exec tmux attach-session -t agy" \
    > /usr/local/bin/agy-entrypoint.sh && \
    chmod +x /usr/local/bin/agy-entrypoint.sh

# Create non-root user matching host UID/GID (1000:1000)
RUN groupadd -g 1000 rahul && \
    useradd -u 1000 -g 1000 -m -s /bin/bash rahul

# User welcome MOTD
RUN echo 'echo -e "\033[1;34m╭────────────────────────────────────────────────────────╮\033[0m"' >> /home/rahul/.bashrc && \
    echo 'echo -e "\033[1;34m│\033[0m \033[1;32mAntigravity Web Terminal\033[0m                               \033[1;34m│\033[0m"' >> /home/rahul/.bashrc && \
    echo 'echo -e "\033[1;34m│\033[0m Workspaces: \033[36m~/docker\033[0m, \033[36m~/projects\033[0m                        \033[1;34m│\033[0m"' >> /home/rahul/.bashrc && \
    echo 'echo -e "\033[1;34m│\033[0m Type \033[1;33magy\033[0m to start Antigravity CLI in current directory  \033[1;34m│\033[0m"' >> /home/rahul/.bashrc && \
    echo 'echo -e "\033[1;34m╰────────────────────────────────────────────────────────╯\033[0m"' >> /home/rahul/.bashrc

USER rahul
WORKDIR /home/rahul

EXPOSE 7681

# ttyd client settings: canvas renderer, Cascadia Mono font, full Catppuccin palette
ENTRYPOINT ["ttyd", \
    "-p", "7681", \
    "-W", \
    "-I", "/usr/local/share/ttyd/index.html", \
    "-t", "rendererType=canvas", \
    "-t", "fontSize=15", \
    "-t", "lineHeight=1.25", \
    "-t", "fontFamily='Cascadia Mono', 'Cascadia Code', Consolas, 'SF Mono', monospace", \
    "-t", "theme={\"background\":\"#1e1e2e\",\"foreground\":\"#cdd6f4\",\"cursor\":\"#f5e0dc\",\"cursorAccent\":\"#11111b\",\"selectionBackground\":\"#585b70\",\"selectionForeground\":\"#cdd6f4\",\"black\":\"#45475a\",\"red\":\"#f38ba8\",\"green\":\"#a6e3a1\",\"yellow\":\"#f9e2af\",\"blue\":\"#89b4fa\",\"magenta\":\"#f5c2e7\",\"cyan\":\"#94e2d5\",\"white\":\"#bac2de\",\"brightBlack\":\"#585b70\",\"brightRed\":\"#f38ba8\",\"brightGreen\":\"#a6e3a1\",\"brightYellow\":\"#f9e2af\",\"brightBlue\":\"#89b4fa\",\"brightMagenta\":\"#f5c2e7\",\"brightCyan\":\"#94e2d5\",\"brightWhite\":\"#a6adc8\"}", \
    "-t", "cursorBlink=true", \
    "-t", "titleFixed=Antigravity Terminal"]

CMD ["/usr/local/bin/agy-entrypoint.sh"]
