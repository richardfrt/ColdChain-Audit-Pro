import csv
import random
from datetime import datetime, timedelta


ARCHIVO_SALIDA = "datos_sensor.csv"
TEMPERATURA_FALLO = 1.5
DURACION_FALLO_MINUTOS = 10
TOTAL_DIAS = 15
MINUTOS_POR_DIA = 24 * 60
TOTAL_REGISTROS = TOTAL_DIAS * MINUTOS_POR_DIA


def generar_temperaturas():
    temperaturas = [round(random.uniform(0.8, 1.1), 2) for _ in range(TOTAL_REGISTROS)]

    max_inicio = TOTAL_REGISTROS - DURACION_FALLO_MINUTOS
    bloques_fallo = []

    while len(bloques_fallo) < 3:
        inicio = random.randint(0, max_inicio)
        fin = inicio + DURACION_FALLO_MINUTOS - 1

        solapa = any(not (fin < bloque_inicio or inicio > bloque_fin) for bloque_inicio, bloque_fin in bloques_fallo)
        if solapa:
            continue

        bloques_fallo.append((inicio, fin))

        for indice in range(inicio, inicio + DURACION_FALLO_MINUTOS):
            temperaturas[indice] = TEMPERATURA_FALLO

    return temperaturas


def escribir_csv(temperaturas):
    inicio_viaje = datetime.now().replace(second=0, microsecond=0)

    with open(ARCHIVO_SALIDA, "w", newline="", encoding="utf-8") as archivo_csv:
        escritor = csv.writer(archivo_csv)
        escritor.writerow(["Fecha_Hora", "Temperatura_C"])

        for minuto, temperatura in enumerate(temperaturas):
            fecha_hora = inicio_viaje + timedelta(minutes=minuto)
            escritor.writerow([fecha_hora.strftime("%Y-%m-%d %H:%M"), temperatura])


def main():
    temperaturas = generar_temperaturas()
    escribir_csv(temperaturas)
    print(f"Archivo generado correctamente: {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    main()
