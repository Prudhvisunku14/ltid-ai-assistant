"""Intentional baseline. Competitors should extend validation, data handling and evaluation."""
import csv

def load_rows(path,city):
    with open(path,encoding='utf-8',newline='') as file:
        rows=[r for r in csv.DictReader(file) if r['city'].casefold()==city.casefold()]
    return sorted(rows,key=lambda r:r['date'])

def predict_temperature(rows,days=3):
    if not rows: raise ValueError('No observations')
    recent=[float(r['temp_c']) for r in rows[-3:]]
    return [round(sum(recent)/len(recent),1)]*days
