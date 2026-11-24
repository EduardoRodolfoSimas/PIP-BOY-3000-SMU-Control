# PIP-BOY 3000 SMU Control

Bem-vindo ao **PIP-BOY 3000 SMU Control**! Este programa controla o **Keysight B2912A Source Measure Unit (SMU)** (ou seu simulador) com uma interface divertida inspirada no *Fallout*, com tela preta e texto verde brilhante. Com ele, você pode aplicar tensões, correntes, medir sinais, gerar ondas, simular cargas ou emular baterias nos dois canais (CH1 e CH2). Salve resultados em **CSV** ou gráficos **PNG** no estilo "PIP-BOY" para análise!

## Por que usar?
- **Fácil**: Menu interativo com instruções claras.
- **Versátil**: Configure tensões, correntes, ondas ou simule baterias para testar circuitos.
- **Visual**: Gráficos em tempo real e arquivos salvos para relatórios.
- **Conexão**: Suporta USB, LAN ou simulador (IP: `127.0.0.1:5025`).

## Pré-requisitos
- **Hardware**: Keysight B2912A SMU ou simulador (`smu_simulator.py`).
- **Software**: Python 3.x, bibliotecas `pyvisa`, `numpy`, `matplotlib`, `colorama`.
- **Conexão**: *Keysight IO Libraries* para USB/LAN (não necessário para simulador).
- **Instalação**: `pip install pyvisa numpy matplotlib colorama`.

## Como usar?
1. Conecte o B2912A via USB ou LAN (ou inicie o simulador).
2. Execute `pip_boy_keysight.py` e escolha USB ou LAN.
3. No menu, selecione uma opção (0 a 10) e siga as instruções.
4. Para emular baterias ([9]), conecte o positivo da placa ao terminal **High** e o negativo ao **Low** de CH1 e CH2.

## Funções do Menu

### [1] Inject Voltage
Aplica tensão fixa (-210V a 210V) em CH1, CH2 ou ambos.  
- **Escolha**: Canal 1, Canal 2 ou ambos.  
- **Mostra**: Tensão e corrente medidas.

### [2] Inject Current
Fornece corrente fixa (-3A a 3A) em CH1, CH2 ou ambos.  
- **Escolha**: Canal 1, Canal 2 ou ambos.  
- **Mostra**: Tensão e corrente medidas.

### [3] Measure & Log
Mede tensão e corrente por um tempo, com gráficos ao vivo.  
- **Escolha**: Canal, duração, intervalo, salvar CSV/gráfico.  
- **Saída**: CSV (tempo, tensão, corrente), PNG (opcional).

### [4] Generate PWM
Gera sinal PWM (onda quadrada) em CH1, CH2 ou ambos.  
- **Escolha**: Amplitude, frequência, ciclo de trabalho, duração.

### [5] Generate Waveform
Cria ondas senoidal, quadrada ou triangular em CH1, CH2 ou ambos.  
- **Escolha**: Tipo de onda, amplitude, frequência, duração.

### [6] Act as Load
Simula carga que consome corrente fixa (-3A a 3A).  
- **Escolha**: Canal 1, Canal 2 ou ambos, corrente da carga.  
- **Mostra**: Tensão e corrente medidas.

### [7] Battery Characterization
Testa bateria real, descarregando até tensão mínima.  
- **Escolha**: Canal, corrente de descarga, tensão mínima, intervalo, CSV/gráfico.  
- **Saída**: CSV (tempo, tensão, corrente), PNG (opcional).

### [8] Continuous Set Points (2 channels)
Aplica tensões diferentes em CH1 e CH2, medindo ao longo do tempo.  
- **Escolha**: Tensões para CH1 e CH2, duração, intervalo, CSV/gráfico.  
- **Saída**: CSV (tempo, tensão, corrente), PNG (opcional).

### [9] Act as Battery
Emula duas baterias independentes (CH1 e CH2) com comportamento realista.  
- **Escolha por canal**: Tensão nominal (ex.: 3,7V), resistência interna (mΩ), capacidade (mAh), tensão mínima.  
- **Escolha compartilhada**: Duração, CSV, gráficos.  
- **Conexão**: Positivo ao CH1/CH2 High, negativo ao CH1/CH2 Low.  
- **Mostra**: Tensão, corrente, SoC (%), carga consumida (mAh) em tempo real.  
- **Saída**: CSV (tempo, tensão, corrente, SoC, carga consumida), PNG com gráficos (tensão, corrente, SoC, consumo com capacidade setada).

### [10] Turn Off Output
Desliga as saídas de CH1 e CH2.

### [0] Exit
Encerra o programa, desligando saídas e conexão.

## Saídas
- **CSV**: Dados com timestamp (ex.: `battery_emulation_20250710_1215.csv`).  
- **PNG**: Gráficos no estilo "PIP-BOY" (fundo preto, linhas verdes), ex.: `battery_emulation_plot_20250710_1215.png`.