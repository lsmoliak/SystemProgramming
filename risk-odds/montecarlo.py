import random, sys
ROLL={(1,1):(36,[15,21]),(1,2):(216,[55,161]),(2,1):(216,[125,91]),(2,2):(1296,[295,420,581]),(3,1):(1296,[855,441]),(3,2):(7776,[2890,2611,2275])}
P={k:[c/t for c in cs] for k,(t,cs) in ROLL.items()}

def fight(mu, d0):
    """mu[a] = P(attacker enters this territory with a attackers). Returns (win[j], lose[k]) for one territory with d0 defenders."""
    A=len(mu)-1
    pi={}
    for a,p in enumerate(mu):
        if p: pi[(a,d0)]=p
    win=[0.0]*(A+1); lose=[0.0]*(d0+1)
    for s in range(A+d0,-1,-1):
        for a in range(min(A,s),-1,-1):
            d=s-a
            if d<0 or d>d0: continue
            p=pi.pop((a,d),0)
            if not p: continue
            if d==0: win[a]+=p; continue
            if a==0: lose[d]+=p; continue
            na,nd=min(3,a),min(2,d); m=min(na,nd)
            for k,q in enumerate(P[(na,nd)]):
                key=(a-k,d-(m-k)); pi[key]=pi.get(key,0)+p*q
    return win,lose

def chain(A,terr):
    """terr = list of defender armies per territory, in attack order. Returns P(win), surplus dist, defender-left dist."""
    T=len(terr); D=sum(terr)
    mu=[0.0]*(A+1); mu[A]=1.0
    defLeft=[0.0]*(D+1)
    for t,dt in enumerate(terr):
        rest=sum(terr[t+1:])
        win,lose=fight(mu,dt)
        for k,p in enumerate(lose): defLeft[k+rest]+=p if k else 0
        mu=[0.0]*(A+1)
        for j,p in enumerate(win):
            if j>=1: mu[j-1]+=p     # garrison 1 in the conquered territory
    surplus=mu                       # after last territory's garrison
    return sum(surplus), surplus, defLeft

def sim(A,terr,rng):
    a=A
    for t,dt in enumerate(terr):
        if a==0: return None, dt+sum(terr[t+1:])
        d=dt
        while a and d:
            x=sorted([rng.randint(1,6) for _ in range(min(3,a))],reverse=True)
            y=sorted([rng.randint(1,6) for _ in range(min(2,d))],reverse=True)
            for i in range(min(len(x),len(y))):
                if x[i]>y[i]: d-=1
                else: a-=1
        if d: return None, d+sum(terr[t+1:])
        a-=1
    return a, 0

def layouts(D,T):
    big=D-T+1
    return [big]+[1]*(T-1), [1]*(T-1)+[big]

rng=random.Random(7); N=int(sys.argv[1]) if len(sys.argv)>1 else 200000
print(f"{'A':>3} {'D':>3} {'T':>2} {'layout':6} {'exact win':>10} {'MC win':>8} {'±2se':>6} {'E[surplus]':>10} {'MC':>7} {'E[defLeft]':>10} {'MC':>7}")
for A,D,T in [(5,3,1),(10,10,1),(8,6,3),(10,8,4),(12,10,5),(6,4,4),(15,12,6)]:
    for name,terr in zip(("front","back"),layouts(D,T)):
        w,sur,dl=chain(A,terr)
        es=sum(j*p for j,p in enumerate(sur)); ed=sum(k*p for k,p in enumerate(dl))
        assert abs(w+sum(dl)-1)<1e-12
        wins=0; ss=0; dd=0
        for _ in range(N):
            s,dleft=sim(A,terr,rng)
            if s is not None: wins+=1; ss+=s
            dd+=dleft
        mw=wins/N; se=(mw*(1-mw)/N)**.5
        print(f"{A:>3} {D:>3} {T:>2} {name:6} {w:10.5f} {mw:8.5f} {2*se:6.4f} {es:10.4f} {ss/N:7.4f} {ed:10.4f} {dd/N:7.4f}")
