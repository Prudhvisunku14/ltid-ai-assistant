import unittest
from pathlib import Path
from weather_app.core import load_rows,predict_temperature
class WeatherStarterTests(unittest.TestCase):
    def test_observations(self):
        file=Path(__file__).resolve().parents[1]/'data'/'weather_history.csv'
        self.assertGreaterEqual(len(load_rows(file,'Tokyo')),20)
    def test_baseline(self):
        self.assertEqual(predict_temperature([{'temp_c':'10'},{'temp_c':'14'},{'temp_c':'15'}],2),[13.0,13.0])
if __name__=='__main__':unittest.main()
