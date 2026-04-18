import pandas as pd


ARCHIVO_DATOS = "datos_sensor.csv"
LIMITE_TEMPERATURA = 1.1


def main():
    datos = pd.read_csv(ARCHIVO_DATOS)
    fallos = datos[datos["Temperatura_C"] > LIMITE_TEMPERATURA]

    total_registros = len(datos)
    temperatura_maxima = datos["Temperatura_C"].max()
    minutos_fuera_rango = len(fallos)

    veredicto = (
        "APTO PARA EXPORTACION"
        if minutos_fuera_rango == 0
        else "CARGAMENTO RECHAZADO"
    )

    print(f"Total de registros analizados: {total_registros}")
    print(f"Temperatura maxima detectada: {temperatura_maxima:.2f} C")
    print(f"Numero de minutos fuera de rango: {minutos_fuera_rango}")
    print(f"VEREDICTO FINAL: {veredicto}")


if __name__ == "__main__":
    main()
