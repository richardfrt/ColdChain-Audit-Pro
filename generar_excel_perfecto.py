from datetime import datetime, timedelta
import csv
import random


def generar_csv_perfecto(nombre_archivo="datos_perfectos.csv", total_filas=43200):
    inicio = datetime(2026, 1, 1, 0, 0, 0)
    indice_pico = total_filas // 2

    with open(nombre_archivo, "w", newline="", encoding="utf-8") as archivo:
        writer = csv.writer(archivo, delimiter=",")
        writer.writerow(["Timestamp", "Temperature"])

        for i in range(total_filas):
            timestamp = (inicio + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
            temperatura = round(random.uniform(0.4, 0.8), 3)
            if i == indice_pico:
                temperatura = 1.5
            writer.writerow([timestamp, temperatura])

    print(f"CSV generado correctamente: {nombre_archivo} ({total_filas} filas)")


if __name__ == "__main__":
    generar_csv_perfecto()
