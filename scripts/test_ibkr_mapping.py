
import logging
from src.data.providers.ibkr import IBKRProvider

# Configure logging to see info
logging.basicConfig(level=logging.INFO)

def test_mapping():
    print("Initializing IBKRProvider with config/symbols.yaml...")
    provider = IBKRProvider(host='127.0.0.1', port=7497, client_id=999)
    
    if not provider.registry:
        print("ERROR: Registry not loaded!")
        return

    test_cases = [
        ("SAN.MC", "SAN", "BME", "EUR"),
        ("ASML.AS", "ASML", "AEB", "EUR"),
        ("SAP.DE", "SAP", "IBIS", "EUR"),
        ("AAPL", "AAPL", "SMART", "USD"),
        ("AZN.L", "AZN", "LSE", "GBP"),
    ]

    print("\nRunning Mapping Tests:")
    
    # DEBUG: Print SAN.MC details
    san = provider.registry.get_by_ticker("SAN.MC")
    if san:
        print(f"DEBUG: SAN.MC object: {san}")
        print(f"DEBUG: ibkr_exchange attr: {getattr(san, 'ibkr_exchange', 'MISSING')}")
    else:
        print("DEBUG: SAN.MC NOT FOUND in registry!")

    all_passed = True
    for input_sym, exp_tick, exp_exch, exp_curr in test_cases:
        contract = provider._create_contract(input_sym)
        passed = (contract.symbol == exp_tick and 
                  contract.exchange == exp_exch and 
                  contract.currency == exp_curr)
        
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
            print(f"FAIL: {input_sym} -> Got({contract.symbol}, {contract.primaryExchange}, {contract.currency}) "
                  f"| Expected({exp_tick}, {exp_exch}, {exp_curr})")
        else:
            print(f"PASS: {input_sym} -> {contract.symbol} on {contract.primaryExchange} ({contract.currency})")
            
    if all_passed:
        print("\nSUCCESS: All mappings validated.")
    else:
        print("\nFAILURE: Some mappings failed.")

if __name__ == "__main__":
    test_mapping()
