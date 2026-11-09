import argparse, json
from .core import load_rows, predict_temperature
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description='Synthetic temperature baseline (not an operational forecast)')
    p.add_argument('--city',required=True)
    p.add_argument('--days',type=int,default=3)
    args=p.parse_args()
    if args.days<1 or args.days>3: p.error('--days must be 1, 2 or 3')
    data=Path(__file__).resolve().parents[1]/'data'/'weather_history.csv'
    rows=load_rows(data,args.city)
    if not rows: p.error('City not present in sample data')
    print(json.dumps({'city':args.city,'days':args.days,'daily_temperature_c':predict_temperature(rows,args.days),'type':'synthetic baseline - educational only'},indent=2))
if __name__=='__main__':main()
