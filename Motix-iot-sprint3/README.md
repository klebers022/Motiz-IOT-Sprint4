# 🏍️ Rastreamento e Monitoramento de Motos – YOLOv8 + ByteTrack + Dashboard Web

Este projeto implementa um **sistema completo de detecção, rastreamento e monitoramento de motocicletas em tempo real**, com visualização via **dashboard web interativo**.  
A detecção é feita com [YOLOv8](https://github.com/ultralytics/ultralytics), o rastreamento com [ByteTrack](https://github.com/ifzhang/ByteTrack), e o painel usa **FastAPI (Python)** + **React (JavaScript)** para exibir a localização, estado e alertas das motos em tempo real.

---

## ✨ Funcionalidades

- 🚦 **Detecção em tempo real** de múltiplas motos em vídeo ou câmera.  
- 🆔 **Rastreamento persistente** com IDs únicos para cada moto.  
- 📍 **Localização no pátio (mapa SVG)** com atualização contínua.  
- 🧭 **Estados automáticos**: em uso, parada, manutenção ou fora da área.  
- 🚨 **Alertas em tempo real** via WebSocket (ocioso, baixa confiança, fora da área).  
- 📊 **Dashboard Web** com:
  - KPIs (totais por estado),
  - mapa do pátio com pontos ativos,
  - lista de alertas recentes,
  - grid com detalhes de cada moto.  
- 🔁 **Loop automático** do vídeo (modo demo).  
- 💾 **Exportação de logs CSV** (timestamp, frame, ID, bbox, confiança).  
- 🧠 **Arquitetura modular**: detecção + servidor + front-end separados.

---

## 🧱 Estrutura do Projeto

```
📂 projeto_motos/
 ┣ 📜 moto_server.py         # Servidor FastAPI + YOLOv8 + ByteTrack + WebSocket
 ┣ 📜 MotoYardDashboard.jsx  # Front-end React (dashboard)
 ┣ 📜 MotoYardDashboard.css  # Estilos do dashboard
 ┣ 📜 track_motos.py         # Versão CLI (rastreamento simples local)
 ┣ 📂 videos/                # Vídeos de teste
 ┗ 📄 README.md
```

---

## 📦 Instalação (Back-end)

### 1. Criar ambiente e instalar dependências

```bash
# criar ambiente virtual
python -m venv .venv
.\.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac

# atualizar pip
pip install --upgrade pip

# instalar pacotes principais
pip install ultralytics supervision opencv-python fastapi uvicorn[standard]
```

### 2. (Opcional) Instalar PyTorch manualmente
Se o YOLO não rodar automaticamente, siga as [instruções oficiais do PyTorch](https://pytorch.org/get-started/locally/).

---

## ▶️ Execução

### 🧠 1. Rodar o servidor de rastreamento
```bash
python moto_server.py
```
Ele vai:
- abrir o vídeo/câmera para detecção e rastreamento,
- iniciar um servidor local (`http://localhost:8000`),
- e transmitir os dados via **WebSocket** (`ws://localhost:8000/ws`).

### 🎥 2. Escolher fonte de vídeo
No início do `moto_server.py` altere:
```python
VIDEO_SOURCE = "0"              # Webcam
# ou
VIDEO_SOURCE = "./videos/teste.mp4"  # Arquivo de vídeo
```
O servidor reinicia o vídeo automaticamente ao chegar ao final.

---

## 💻 Front-end (Dashboard Web)

### 1. Criar projeto React
```bash
npm create vite@latest motos-dashboard -- --template react
cd motos-dashboard
npm install
```

### 2. Adicionar os arquivos
Copie para `src/`:
- `MotoYardDashboard.jsx`
- `MotoYardDashboard.css`

Edite `src/App.jsx`:
```jsx
import MotoYardDashboard from './MotoYardDashboard';
export default function App() {
  return <MotoYardDashboard />;
}
```

### 3. Rodar o front-end
```bash
npm run dev
```
Abra o link (geralmente `http://localhost:5173`)  
O painel tentará se conectar automaticamente a `ws://localhost:8000/ws`.

---

## 🧠 Tecnologias Utilizadas

| Camada | Tecnologia | Função |
|--------|-------------|--------|
| **IA / Visão Computacional** | [YOLOv8](https://github.com/ultralytics/ultralytics) | Detecção de motos em vídeo |
|  | [ByteTrack](https://github.com/ifzhang/ByteTrack) | Rastreamento com IDs persistentes |
| **Processamento de Vídeo** | OpenCV | Leitura, exibição e desenho de detecções |
| **Servidor** | FastAPI + Uvicorn | API e WebSocket em tempo real |
| **Comunicação** | WebSocket | Envio contínuo de dados para o front-end |
| **Interface Web** | React.js (via Vite) | Dashboard interativo |
| **Estilo** | CSS puro | Layout responsivo e leve |
| **Execução Paralela** | Threading Python | Roda IA + servidor simultaneamente |

---

## 📊 Visualizações no Dashboard

- **Mapa do pátio:** pontos das motos com cores por estado  
  🟢 em uso • ⚪ parada • 🟡 manutenção • 🔴 fora da área  
- **KPIs superiores:** totais e contagens por categoria  
- **Alertas recentes:** lista de eventos com timestamp  
- **Grade de motos:** dados detalhados de cada ID ativo  

---

## 📹 Vídeos para Teste

- [Pixabay – Motorcycle Videos](https://pixabay.com/videos/search/motorcycle/)
- [Pexels – Motorcycle Clips](https://www.pexels.com/search/videos/motorcycle/)
- [Mixkit – Free Motorcycle Footage](https://mixkit.co/free-stock-video/motorcycle/)

---

## 👥 Participantes

| Nome               | RM      |
|--------------------|---------|
| Kleber da Silva    | 557887  |
| Nicolas Barutti    | 554944  |
| Lucas Rainha       | 558471  |

---

## 📄 Licença
Este projeto é open-source sob a licença **MIT**.  
Sinta-se livre para adaptar e expandir conforme suas necessidades.
