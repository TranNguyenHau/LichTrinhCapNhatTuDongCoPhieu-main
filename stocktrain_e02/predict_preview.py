"""Preview real bundle inference from DB; never writes predictions. Useful first smoke test."""
import argparse
from .config import connection, MODEL_NAMES, SYMBOLS
from .model_service import run_symbol

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--symbol', default='FPT', choices=SYMBOLS)
    parser.add_argument('--model',default='LinearRegression', choices=MODEL_NAMES)
    args=parser.parse_args()
    conn=connection()
    try:
        result=run_symbol(conn,args.symbol,[args.model])[0]
        print('As of:',result['as_of'],'symbol:',result['symbol'],'model:',result['model'])
        print('Predicted 5-session return:',round(100*result['predicted_return'],4),'%')
        print('Trend:',result['trend'],'descriptive risk:',result['risk_level'])
        print('Model trained until:',result['trained_until'])
        print('Warnings:',result['warnings'])
        print('NOT SAVED; database remains unchanged')
    finally:
        conn.close()

if __name__=='__main__':
    main()
