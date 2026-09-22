import json, urllib.request, time, collections, sys, re
BASE="https://api.elections.kalshi.com/trade-api/v2"; SP=sys.argv[1]
def get(p):
    r=urllib.request.Request(BASE+p,headers={"User-Agent":"phase0-discovery"})
    with urllib.request.urlopen(r,timeout=30) as f: return json.load(f)
def F(m,k): 
    try: return float(m.get(k) or 0)
    except: return 0.0

series=json.load(open(SP+"/series.json"))["series"]
targets=[x for x in series if x["ticker"].startswith(("KXHIGH","KXLOW","HIGH"))
         and (x.get("tags") or [None])[0]=="Daily temperature" and x["frequency"]=="daily"]
rows=[]; allm={}
for s in targets:
    t=s["ticker"]
    try: m=get(f"/markets?series_ticker={t}&status=open&limit=200")["markets"]
    except Exception as e: print("ERR",t,e); continue
    if not m: continue
    allm[t]=m
    spreads=[]
    for x in m:
        b,a=F(x,"yes_bid_dollars"),F(x,"yes_ask_dollars")
        if b>0 and a>0 and a>b: spreads.append(a-b)
    # station id from rules text
    stn=""
    mm=re.search(r'recorded at ([^,]+?) \(([A-Z0-9]+)\)', m[0].get("rules_primary",""))
    if mm: stn=f"{mm.group(1)} ({mm.group(2)})"
    rows.append(dict(ticker=t,title=s["title"],
        src=",".join(ss["name"] for ss in (s.get("settlement_sources") or [])),
        station=stn, n=len(m), evts=len(set(x["event_ticker"] for x in m)),
        vol=sum(F(x,"volume_fp") for x in m), v24=sum(F(x,"volume_24h_fp") for x in m),
        oi=sum(F(x,"open_interest_fp") for x in m), quoted=len(spreads),
        medspread=sorted(spreads)[len(spreads)//2] if spreads else None,
        rules=m[0].get("rules_primary","")))
    time.sleep(0.12)
json.dump({"rows":rows,"markets":allm},open(SP+"/probe2.json","w"))
rows.sort(key=lambda x:-x["v24"])
print(f"{'series':<13}{'mkts':>5}{'ev':>3}{'quo':>4}{'vol24h':>9}{'openint':>9}{'spread':>7}  {'station':<26} source")
for x in rows:
    sp=f"{x['medspread']*100:.0f}c" if x['medspread'] else "-"
    print(f"{x['ticker']:<13}{x['n']:>5}{x['evts']:>3}{x['quoted']:>4}{x['v24']:>9,.0f}{x['oi']:>9,.0f}{sp:>7}  {x['station'][:26]:<26} {x['src']}")
print("\nTOTAL 24h volume across daily temp series:",f"{sum(x['v24'] for x in rows):,.0f}")
