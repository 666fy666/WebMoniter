#!/bin/bash
# 日志清理脚本
# 删除超过3天的日志文件

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 日志目录
LOG_DIR="$PROJECT_DIR/logs"

# 设置日志文件路径（用于记录清理操作）
CLEANUP_LOG="$LOG_DIR/cleanup.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 记录清理开始时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始清理超过3天的日志文件..." >> "$CLEANUP_LOG"

# 查找并删除超过3天的日志文件
# -mtime +3 表示修改时间超过3天（即4天前及更早的文件）
# -type f 只查找文件
# -name "*.log" 只匹配.log文件
DELETED_COUNT=0
while IFS= read -r -d '' file; do
    if rm -f "$file"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已删除: $(basename "$file")" >> "$CLEANUP_LOG"
        ((DELETED_COUNT++))
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 删除失败: $(basename "$file")" >> "$CLEANUP_LOG"
    fi
done < <(find "$LOG_DIR" -type f -name "*.log" -mtime +3 -print0 2>/dev/null)

# 记录清理结果
if [ $DELETED_COUNT -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 清理完成: 没有需要删除的日志文件" >> "$CLEANUP_LOG"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 清理完成: 共删除 $DELETED_COUNT 个日志文件" >> "$CLEANUP_LOG"
fi

# 清理cleanup.log本身（如果超过30天）
find "$LOG_DIR" -name "cleanup.log" -mtime +30 -delete 2>/dev/null

exit 0

