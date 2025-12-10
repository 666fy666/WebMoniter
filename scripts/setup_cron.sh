#!/bin/bash
# Cron定时任务安装脚本
# 用于自动配置Ubuntu的cron定时任务

set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 包装脚本的绝对路径
HUYA_SCRIPT="$SCRIPT_DIR/run_huya.sh"
WEIBO_SCRIPT="$SCRIPT_DIR/run_weibo.sh"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_logs.sh"

# 检查脚本文件是否存在
if [ ! -f "$HUYA_SCRIPT" ]; then
    echo "错误: 找不到 $HUYA_SCRIPT"
    exit 1
fi

if [ ! -f "$WEIBO_SCRIPT" ]; then
    echo "错误: 找不到 $WEIBO_SCRIPT"
    exit 1
fi

if [ ! -f "$CLEANUP_SCRIPT" ]; then
    echo "错误: 找不到 $CLEANUP_SCRIPT"
    exit 1
fi

# 确保脚本有执行权限
chmod +x "$HUYA_SCRIPT"
chmod +x "$WEIBO_SCRIPT"
chmod +x "$CLEANUP_SCRIPT"

echo "=========================================="
echo "Web监控系统 - Cron定时任务安装"
echo "=========================================="
echo ""
echo "项目目录: $PROJECT_DIR"
echo "虎牙监控脚本: $HUYA_SCRIPT"
echo "微博监控脚本: $WEIBO_SCRIPT"
echo "日志清理脚本: $CLEANUP_SCRIPT"
echo ""

# 创建临时crontab文件
TEMP_CRON=$(mktemp)

# 备份现有crontab（如果存在）
if crontab -l >/dev/null 2>&1; then
    echo "备份现有crontab配置..."
    crontab -l > "$TEMP_CRON"
    echo "" >> "$TEMP_CRON"
else
    echo "创建新的crontab配置..."
fi

# 添加项目标识注释
echo "# ========================================" >> "$TEMP_CRON"
echo "# Web监控系统定时任务" >> "$TEMP_CRON"
echo "# 项目路径: $PROJECT_DIR" >> "$TEMP_CRON"
echo "# 安装时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$TEMP_CRON"
echo "# ========================================" >> "$TEMP_CRON"
echo "" >> "$TEMP_CRON"

# 检查是否已存在相关任务
if grep -q "run_huya.sh" "$TEMP_CRON" 2>/dev/null; then
    echo "⚠️  检测到已存在的虎牙监控任务，将跳过添加"
else
    # 虎牙监控：每2分钟执行一次
    echo "# 虎牙直播监控 - 每2分钟执行一次" >> "$TEMP_CRON"
    echo "*/2 * * * * $HUYA_SCRIPT" >> "$TEMP_CRON"
    echo "" >> "$TEMP_CRON"
    echo "✅ 已添加虎牙监控任务（每2分钟执行一次）"
fi

if grep -q "run_weibo.sh" "$TEMP_CRON" 2>/dev/null; then
    echo "⚠️  检测到已存在的微博监控任务，将跳过添加"
else
    # 微博监控：每5分钟执行一次
    echo "# 微博监控 - 每5分钟执行一次" >> "$TEMP_CRON"
    echo "*/5 * * * * $WEIBO_SCRIPT" >> "$TEMP_CRON"
    echo "" >> "$TEMP_CRON"
    echo "✅ 已添加微博监控任务（每5分钟执行一次）"
fi

if grep -q "cleanup_logs.sh" "$TEMP_CRON" 2>/dev/null; then
    echo "⚠️  检测到已存在的日志清理任务，将跳过添加"
else
    # 日志清理：每天凌晨2点执行，删除超过3天的日志
    echo "# 日志清理 - 每天凌晨2点执行，删除超过3天的日志文件" >> "$TEMP_CRON"
    echo "0 2 * * * $CLEANUP_SCRIPT" >> "$TEMP_CRON"
    echo "" >> "$TEMP_CRON"
    echo "✅ 已添加日志清理任务（每天凌晨2点执行，删除超过3天的日志）"
fi

# 安装crontab
echo ""
echo "正在安装crontab配置..."
crontab "$TEMP_CRON"

# 清理临时文件
rm "$TEMP_CRON"

echo ""
echo "=========================================="
echo "✅ Cron定时任务安装完成！"
echo "=========================================="
echo ""
echo "当前crontab配置："
echo "----------------------------------------"
crontab -l | grep -A 10 "Web监控系统"
echo "----------------------------------------"
echo ""
echo "查看所有crontab任务: crontab -l"
echo "编辑crontab任务: crontab -e"
echo "删除所有crontab任务: crontab -r"
echo ""
echo "日志文件位置:"
echo "  - 虎牙监控: $PROJECT_DIR/logs/huya_YYYYMMDD.log"
echo "  - 微博监控: $PROJECT_DIR/logs/weibo_YYYYMMDD.log"
echo "  - 清理日志: $PROJECT_DIR/logs/cleanup.log"
echo ""
echo "日志清理策略:"
echo "  - 自动删除超过3天的日志文件"
echo "  - 每天凌晨2点自动执行清理"
echo ""
echo "查看cron服务状态: systemctl status cron"
echo "查看cron日志: grep CRON /var/log/syslog"
echo ""

