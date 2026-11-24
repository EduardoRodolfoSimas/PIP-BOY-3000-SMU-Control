import socket
import random
import time


# Simulador de Keysight B2912A
class SMUSimulator:
    def __init__(self, host='127.0.0.1', port=5025):
        self.host = host
        self.port = port
        self.source_mode = {1: 'VOLT', 2: 'VOLT'}  # Modo padrão: tensão
        self.voltage_level = {1: 0.0, 2: 0.0}  # Níveis de tensão
        self.current_level = {1: 0.0, 2: 0.0}  # Níveis de corrente
        self.current_protection = {1: 0.1, 2: 0.1}  # Limite de corrente padrão
        self.voltage_protection = {1: 5.0, 2: 5.0}  # Limite de tensão padrão
        self.output_state = {1: False, 2: False}  # Estado da saída (OFF por padrão)
        self.error_queue = []  # Fila de erros
        self.sense_functions = {1: ['VOLT', 'CURR'], 2: ['VOLT', 'CURR']}  # Funções de medição
        self.aperture_time = {1: {'VOLT': 0.0001, 'CURR': 0.0001},
                              2: {'VOLT': 0.0001, 'CURR': 0.0001}}  # Tempo de abertura

    def add_error(self, code, message):
        self.error_queue.append(f"{code},\"{message}\"")

    def reset(self):
        self.source_mode = {1: 'VOLT', 2: 'VOLT'}
        self.voltage_level = {1: 0.0, 2: 0.0}
        self.current_level = {1: 0.0, 2: 0.0}
        self.current_protection = {1: 0.1, 2: 0.1}
        self.voltage_protection = {1: 5.0, 2: 5.0}
        self.output_state = {1: False, 2: False}
        self.aperture_time = {1: {'VOLT': 0.0001, 'CURR': 0.0001}, 2: {'VOLT': 0.0001, 'CURR': 0.0001}}
        self.error_queue = []

    def simulate_measurement(self, channel, parameter):
        # Simula medição com pequeno ruído
        if not self.output_state[channel]:
            return 0.0
        if parameter == 'VOLT':
            value = self.voltage_level[channel] if self.source_mode[channel] == 'VOLT' else self.current_level[
                                                                                                channel] * 10.0
            noise = random.gauss(0, 0.001)  # Ruído de ±1mV
            return max(min(value + noise, self.voltage_protection[channel]), -self.voltage_protection[channel])
        else:  # CURR
            value = self.current_level[channel] if self.source_mode[channel] == 'CURR' else self.voltage_level[
                                                                                                channel] / 10.0
            noise = random.gauss(0, 0.0001)  # Ruído de ±100µA
            return max(min(value + noise, self.current_protection[channel]), -self.current_protection[channel])

    def process_command(self, command):
        command = command.strip()
        print(f"Received: {command}")

        if command == '*IDN?':
            return "Keysight Technologies,B2912A,Simulated,1.0\n"

        if command == '*CLS':
            self.error_queue = []
            return ""

        if command == '*RST':
            self.reset()
            return ""

        if command == ':SYST:ERR?':
            if self.error_queue:
                return self.error_queue.pop(0) + '\n'
            return "+0,\"No error\"\n"

        # Comandos de fonte
        if command.startswith(':SOUR'):
            parts = command.split(':')
            if len(parts) < 3:
                self.add_error(-113, "Undefined header")
                return ""
            channel = int(parts[1][4]) if parts[1].startswith('SOUR') else 1
            if channel not in [1, 2]:
                self.add_error(-221, "Settings conflict; Invalid channel")
                return ""

            if ':FUNC' in command:
                mode = command.split()[-1]
                if mode in ['VOLT', 'CURR']:
                    self.source_mode[channel] = mode
                else:
                    self.add_error(-221, "Settings conflict; Invalid mode")
                return ""

            if ':VOLT' in command:
                try:
                    level = float(command.split()[-1])
                    if abs(level) > 210:  # Limite máximo de tensão do B2912A
                        self.add_error(-222, "Data out of range")
                    else:
                        self.voltage_level[channel] = level
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

            if ':CURR' in command:
                try:
                    level = float(command.split()[-1])
                    if abs(level) > 10:  # Limite máximo de corrente do B2912A
                        self.add_error(-222, "Data out of range")
                    else:
                        self.current_level[channel] = level
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

        # Comandos de sense
        if command.startswith(':SENS'):
            parts = command.split(':')
            channel = int(parts[1][4]) if parts[1].startswith('SENS') else 1
            if channel not in [1, 2]:
                self.add_error(-221, "Settings conflict; Invalid channel")
                return ""

            if ':CURR:PROT' in command:
                try:
                    level = float(command.split()[-1])
                    if level <= 0 or level > 10:
                        self.add_error(-222, "Data out of range")
                    else:
                        self.current_protection[channel] = level
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

            if ':VOLT:PROT' in command:
                try:
                    level = float(command.split()[-1])
                    if level <= 0 or level > 210:
                        self.add_error(-222, "Data out of range")
                    else:
                        self.voltage_protection[channel] = level
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

            if ':FUNC' in command:
                func = command.split('"')[1] if '"' in command else command.split()[-1]
                if func in ['VOLT', 'CURR']:
                    if func not in self.sense_functions[channel]:
                        self.sense_functions[channel].append(func)
                else:
                    self.add_error(-221, "Settings conflict; Invalid function")
                return ""

            if ':VOLT:APER' in command:
                try:
                    aperture = float(command.split()[-1])
                    if aperture < 0.00002 or aperture > 0.2:
                        self.add_error(-222, "Data out of range")
                    else:
                        self.aperture_time[channel]['VOLT'] = aperture
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

            if ':CURR:APER' in command:
                try:
                    aperture = float(command.split()[-1])
                    if aperture < 0.00002 or aperture > 0.2:
                        self.add_error(-222, "Data out of range")
                    else:
                        self.aperture_time[channel]['CURR'] = aperture
                except ValueError:
                    self.add_error(-103, "Invalid numeric parameter")
                return ""

        # Comandos de saída
        if command.startswith(':OUTP'):
            parts = command.split(':')
            channel = int(parts[1][4]) if parts[1].startswith('OUTP') else 1
            if channel not in [1, 2]:
                self.add_error(-221, "Settings conflict; Invalid channel")
                return ""
            state = command.split()[-1]
            if state in ['ON', '1']:
                self.output_state[channel] = True
            elif state in ['OFF', '0']:
                self.output_state[channel] = False
            else:
                self.add_error(-221, "Settings conflict; Invalid state")
            return ""

        # Comandos de medição
        if command.startswith(':MEAS'):
            parts = command.split(':')
            channel = int(command.split('(@')[1][0]) if '(@' in command else 1
            if channel not in [1, 2]:
                self.add_error(-221, "Settings conflict; Invalid channel")
                return ""
            if ':VOLT?' in command:
                time.sleep(self.aperture_time[channel]['VOLT'])  # Simula tempo de medição
                return f"{self.simulate_measurement(channel, 'VOLT'):.6E}\n"
            if ':CURR?' in command:
                time.sleep(self.aperture_time[channel]['CURR'])  # Simula tempo de medição
                return f"{self.simulate_measurement(channel, 'CURR'):.6E}\n"

        self.add_error(-113, "Undefined header")
        return ""

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)
        print(f"SMU Simulator listening on {self.host}:{self.port}...")

        while True:
            try:
                client_socket, addr = server_socket.accept()
                print(f"Connected to {addr}")
                client_socket.settimeout(20.0)
                buffer = ""
                while True:
                    try:
                        data = client_socket.recv(1024).decode('ascii')
                        if not data:
                            break
                        buffer += data
                        while '\n' in buffer:
                            cmd, buffer = buffer.split('\n', 1)
                            response = self.process_command(cmd)
                            if response:
                                client_socket.send(response.encode('ascii'))
                    except socket.timeout:
                        print("Client timeout")
                        break
                    except Exception as e:
                        print(f"Error: {e}")
                        break
                client_socket.close()
                print(f"Disconnected from {addr}")
            except KeyboardInterrupt:
                print("\nShutting down simulator...")
                break
            except Exception as e:
                print(f"Server error: {e}")
        server_socket.close()


if __name__ == "__main__":
    simulator = SMUSimulator()
    simulator.start_server()