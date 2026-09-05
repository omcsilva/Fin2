"""Retired: Fin2 obtains benchmark histories from official sources."""
import argparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database')
    parser.add_argument('--batch')
    parser.parse_args()
    parser.exit(2,'Carga de índices pela brapi desativada. Use scripts.update_official_benchmarks.\n')


if __name__=='__main__':
    main()
