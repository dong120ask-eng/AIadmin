"""Offline ecommerce calculations. No platform writes. JSON contracts in tool-contract.md."""
import argparse, json, math
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

def number(row,key,integer=False):
    if key not in row or isinstance(row[key],bool): raise ValueError('missing/invalid '+key)
    try: value=Decimal(str(row[key]))
    except Exception: raise ValueError('invalid '+key)
    if not value.is_finite() or value<0: raise ValueError('nonnegative finite value required: '+key)
    if integer and value!=value.to_integral_value(): raise ValueError('integer required: '+key)
    return value

def money(x):return str(x.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
def ratio(a,b):return None if b==0 else str((a/b).quantize(Decimal('.000001')))
def ident(row,key):
    value=row.get(key)
    if not isinstance(value,str) or not value.strip():raise ValueError('identifier required: '+key)
    return value

def calculate(mode,data):
    rows=data.get('rows')
    if not isinstance(rows,list) or not rows:raise ValueError('nonempty rows required')
    result={'status':'offline_calculated','source_label':data.get('source_label','unspecified'),'mode':mode,'results':[]}
    if mode=='profit':
        seen=set();total=Decimal(0)
        fields=['net_revenue','merchant_subsidy','goods_cost','platform_fees','ad_spend','fulfillment_cost','after_sales_net_loss','other_variable_cost']
        for r in rows:
            key=ident(r,'record_id')
            if key in seen:raise ValueError('duplicate record_id')
            seen.add(key);v={f:number(r,f) for f in fields}
            p=v['net_revenue']+v['merchant_subsidy']-sum(v[f] for f in fields[2:]);total+=p
            result['results'].append({'record_id':key,'sku':ident(r,'sku'),'contribution_profit':money(p),'ad_roas':ratio(v['net_revenue'],v['ad_spend']),'loss':p<0})
        result['total_contribution_profit']=money(total)
        result['limitation']='Contribution profit excludes fixed costs and tax unless explicitly included in input. Not cash flow or net profit.'
    elif mode=='promotion':
        for r in rows:
            amount=number(r,'unit_price')*number(r,'quantity',True)
            if number(r,'quantity',True)==0:raise ValueError('quantity must be positive')
            operations=r.get('operations')
            if not isinstance(operations,list):raise ValueError('explicit ordered operations required')
            initial=amount
            for op in operations:
                # only merchant-funded discounts; merchant subsidy supplied separately
                kind=op.get('type')
                if kind=='multiply':
                    factor=number(op,'factor')
                    if factor>1:raise ValueError('factor must be <= 1')
                    amount=Decimal(money(amount*factor))
                elif kind=='subtract':
                    threshold=number(op,'threshold');discount=number(op,'amount')
                    basis=op.get('threshold_basis')
                    if basis not in ('initial','current'):raise ValueError('threshold_basis must be initial/current')
                    if (initial if basis=='initial' else amount)>=threshold:amount=max(Decimal(0),amount-discount)
                else:raise ValueError('unsupported promotion operation')
            profit=amount+number(r,'merchant_subsidy')-number(r,'total_variable_cost')
            result['results'].append({'scenario_id':ident(r,'scenario_id'),'payable':money(amount),'profit':money(profit),'below_floor':amount/number(r,'quantity',True)<number(r,'unit_price_floor'),'loss':profit<0})
        result['limitation']='Only explicitly supplied allowed scenarios and order evaluated; does not discover platform stacking rules. Verify platform preview.'
    elif mode=='inventory':
        seen=set()
        for r in rows:
            sku=ident(r,'sku')
            if sku in seen:raise ValueError('one row per physical SKU required')
            seen.add(sku)
            available=max(Decimal(0),number(r,'on_hand',True)-number(r,'reserved',True)-number(r,'safety',True))
            remaining=available;alloc=[];stores=set()
            for request in r.get('requests',[]):
                store=ident(request,'store_id')
                if store in stores:raise ValueError('duplicate store request')
                stores.add(store);demand=number(request,'requested',True);grant=min(demand,remaining);remaining-=grant
                alloc.append({'store_id':store,'allocated':int(grant),'unmet':int(demand-grant)})
            result['results'].append({'sku':sku,'available':int(available),'allocations':alloc,'unallocated':int(remaining)})
        result['limitation']='Snapshot proposal in input priority order; not live reservation or synchronization. Revalidate before execution.'
    elif mode=='funnel':
        for r in rows:
            v={k:number(r,k,True) for k in ['impressions','clicks','visitors','cart_users','buyers']}
            if v['clicks']>v['impressions'] or v['cart_users']>v['visitors'] or v['buyers']>v['visitors']:raise ValueError('inconsistent same-window funnel counts')
            result['results'].append({'channel':ident(r,'channel'),'ctr':ratio(v['clicks'],v['impressions']),'cart_rate':ratio(v['cart_users'],v['visitors']),'buyer_rate':ratio(v['buyers'],v['visitors']),'visitors':int(v['visitors']),'buyers':int(v['buyers'])})
        result['limitation']='Same-window counts only; channel visitors may overlap. No causal diagnosis or cross-channel deduplication.'
    elif mode=='after_sales':
        seen=set();groups=defaultdict(lambda:[0,Decimal(0)])
        for r in rows:
            case=ident(r,'case_id')
            if case in seen:raise ValueError('duplicate case_id')
            seen.add(case);key=(ident(r,'sku'),ident(r,'reason'));groups[key][0]+=1;groups[key][1]+=number(r,'refund_amount')
        result['results']=[{'sku':k[0],'reason':k[1],'case_count':v[0],'refund_amount':money(v[1])} for k,v in sorted(groups.items())]
        result['limitation']='Counts and amounts only; refund rate needs matching order denominator and maturity. Reason is reported label, not proven root cause.'
    else:raise ValueError('unknown mode')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['profit','promotion','inventory','funnel','after_sales']);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:
        with open(a.input,encoding='utf-8-sig') as f:data=json.load(f)
        result=calculate(a.mode,data)
        # fail without modifying an existing output; user chooses a new path
        with open(a.output,'x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    except (ValueError,KeyError,TypeError,OSError) as e:p.exit(2,'ERROR: '+str(e)+'\n')
if __name__=='__main__':main()
