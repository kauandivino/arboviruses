"""Testes de domínio das coordenadas; não inferir nem corrigir geolocalização."""
import unittest
from processar_cnes import coordinate_status


class CoordenadasCNES(unittest.TestCase):
    def test_ausencias(self):
        for lat, lon in [('', '-49'), ('-16', ''), (None, '-49')]:
            self.assertEqual(coordinate_status(lat, lon)[2], 'ausente')

    def test_numeros(self):
        self.assertEqual(coordinate_status('-16,6', '-49,2'), (-16.6, -49.2, 'dominio_valido'))
        for lat, lon, status in [('x', '-49', 'nao_numerica'), ('91', '-49', 'fora_dominio'),
                                 ('-16', '-181', 'fora_dominio'), ('0', '0', 'zero_suspeito'),
                                 ('NaN', '-49', 'fora_dominio')]:
            self.assertEqual(coordinate_status(lat, lon)[2], status)

    def test_nao_inverte_coordenadas(self):
        self.assertEqual(coordinate_status('-49.2', '-16.6'), (-49.2, -16.6, 'dominio_valido'))
        # Domínio mundial válido não equivale a localização dentro de Goiânia.


if __name__ == '__main__':
    unittest.main()
