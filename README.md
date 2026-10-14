# KoboldCpp-IDE

> Interfaz web alternativa para [KoboldCpp](https://github.com/LostRuins/koboldcpp), orientada a **programación generalista** y **hardware modesto** (portátiles con iGPU).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![KoboldCpp](https://img.shields.io/badge/KoboldCpp-compatible-4ec9b0.svg)](https://github.com/LostRuins/koboldcpp)

---

## 📖 Descripción

**KoboldCpp-IDE** es una interfaz web ligera que se apoya en el motor de inferencia [KoboldCpp](https://github.com/LostRuins/koboldcpp) para ofrecer una experiencia de **agente de programación local**.

Mientras que la interfaz original de KoboldCpp (KoboldAI Lite) está orientada a **escritura creativa y roleplay**, este proyecto ofrece una alternativa enfocada en:

- **Programación generalista** con un agente que puede leer, escribir y ejecutar código
- **Hardware modesto**: optimizado para portátiles con GPU integrada (iGPU)
- **Flujo agéntico real**: el modelo no solo conversa, ejecuta acciones
- **Control total del prompt del sistema** por sesión
- **Sandbox de seguridad** para evitar que el agente haga cosas peligrosas

Todo ello funcionando **100% en local**, sin dependencias de la nube y sin enviar datos a terceros.

---

## 🎯 Motivación

Este proyecto nace de una necesidad concreta: **usar modelos LLM locales como asistente de programación en un portátil modesto**.

Las alternativas existentes (Cursor, GitHub Copilot, Cline, Cursor, Bodega, etc.) presentan problemas en este contexto:

| Herramienta | Problema para hardware modesto |
|---|---|
| **GitHub Copilot (BYOK)** | Timeouts de 8s, dependencia de la nube |
| **Cursor** | Requiere conexión a internet, no soporta endpoints locales sin túnel |
| **Bodega One Code** | Backend roto en CLI, timeouts agresivos |
| **Cline / Roo Code / Kilo Code** | Timeout de 5min de `undici`, prompts gigantes |
| **Aider** | Funciona, pero es correoso y poco automático |

**KoboldCpp-IDE** nace como respuesta: un dashboard web propio, sin timeouts ajenos, sin dependencias opacas, y adaptado al hardware real.

---

## ✨ Características

- 💬 **Chat con streaming en vivo** — ves al modelo escribir token a token
- 🔧 **Tool calling nativo** — el agente puede ejecutar:
  - `read_file` — leer archivos del proyecto
  - `write_file` — crear y modificar archivos
  - `list_dir` — explorar directorios
  - `run_command` — ejecutar comandos shell
- 📁 **Gestor de archivos** con árbol navegable
- ✏️ **Editor de código (Monaco)** con syntax highlighting, pestañas y guardado con `Ctrl+S`
- 📝 **System prompt editable por sesión** — cada sesión puede tener su propio "prompt madre"
- 🗂️ **Workspace configurable por sesión** — apunta a un directorio distinto en cada sesión
- 💾 **Persistencia en SQLite** — historial completo de conversaciones
- 🔒 **Sandbox de seguridad**:
  - Bloqueo de comandos peligrosos (`sudo`, `rm -rf /`, `mkfs`, etc.)
  - Aislamiento de rutas: el agente solo puede tocar archivos dentro del workspace
  - Timeout de 60s en comandos
- ⚡ **Sin dependencias de Node.js/npm** — solo Python + FastAPI

---

## 🖥️ Hardware probado

Este proyecto ha sido desarrollado y probado en:

- **Portátil**: CPU AMD Ryzen 7 + iGPU Radeon 680M (Vulkan)
- **Modelo**: `Qwen2.5-Coder-7B-Instruct` (GGUF, Q4_K_M)
- **Velocidad**: ~9 tokens/s de generación, ~120-170 T/s de prompt processing
- **RAM**: 29 GB compartida entre CPU e iGPU

Funciona también en:
- CPU sin GPU dedicada (más lento)
- GPU dedicada NVIDIA (más rápido, requiere CUDA)
- AMD dedicada (requiere ROCm o Vulkan)

---

## 🚀 Instalación

### Requisitos previos

1. **KoboldCpp** funcionando con un modelo GGUF que soporte tool calling
2. **Python 3.10+**
3. **Git**

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/Ydalgo/KoboldCpp-IDE.git
cd KoboldCpp-IDE
