#!/bin/bash
# 微博监控运行脚本
# 用于cron定时任务，确保环境变量和路径正确

# 设置PATH环境变量，确保能找到uv等命令
# cron执行时PATH通常不包含用户目录，需要手动设置
export PATH="/home/fengyu/.local/bin:$PATH"
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 切换到项目目录
cd "$PROJECT_DIR" || exit 1

# 设置日志文件路径
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/weibo_$(date +%Y%m%d).log"

# 检查uv命令是否可用
if ! command -v uv &> /dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 找不到uv命令，请确保uv已安装并在PATH中" >> "$LOG_FILE"
    echo "当前PATH: $PATH" >> "$LOG_FILE"
    exit 1
fi

# 执行监控脚本，将输出追加到日志文件
# 使用 uv run 运行，uv会自动加载.env文件
uv run python weibo.py >> "$LOG_FILE" 2>&1

# 记录执行时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 微博监控执行完成，退出码: $?" >> "$LOG_FILE"

