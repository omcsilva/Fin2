"""Retired: Fin2 no longer downloads full asset histories from brapi."""
import argparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database')
    parser.add_argument('--batch')
    parser.parse_args()
    parser.exit(2,'Carga histórica pela brapi desativada. Use o botão do Fin2 para consultar somente o último fechamento.\n')


if __name__=='__main__':
    main()
