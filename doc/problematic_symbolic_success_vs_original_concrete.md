# Problematic Symbolic Success DL Rules vs Original Concrete

Source symbolic: fixed symbolic CEX-blocking runs, choosing the latest successful rerun per benchmark.
Source concrete: original synthesis-artifact-20250327 concrete run at commit fe39ebc, directory `experiments/original-concrete-fe39ebc-timeout300-v2`.

## erc20

- Symbolic result: `success`, time `543.233`, iterations `31`, timeout run `900s`.
- Note: Symbolic transferFrom contains totalSupply == 0; original concrete transferFrom checks allowance and owner balance.

### Fixed symbolic final DL transaction rules

```prolog
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- 0!=balanceOf_x1_0,totalSupply(totalSupply_n_1),0==totalSupply_n_1,recv_transferFrom(o,r,s,n),balanceOf(s,balanceOf_x1_0).
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
```

### Original concrete final DL transaction rules

```prolog
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- allowance(o,s,allowance_x2_1),n<allowance_x2_1,balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n>=0,n<balanceOf_x1_2.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>0.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
```

## matic

- Symbolic result: `success`, time `969.095`, iterations `37`, timeout run `1200s`.
- Note: Symbolic transferFrom checks recipient balance and n > totalSupply; original concrete checks paused, allowance, and owner balance.

### Fixed symbolic final DL transaction rules

```prolog
decreaseAllowance(o,s,n) :- recv_decreaseAllowance(o,s,n),allowance(o,s,allowance_x2),n<=allowance_x2.
burn(p,n) :- msgSender(s),n<balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
increaseAllowance(o,s,n) :- recv_increaseAllowance(o,s,n),n>=0.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),paused(b),b!=true,n<balanceOf_x1_1,n>=0.
mint(p,n) :- msgSender(s),n>0,recv_mint(p,n),o==s,owner(o).
unpause() :- recv_unpause().
transferFrom(o,r,s,n) :- n>totalSupply_n_1,n<balanceOf_x1_0,balanceOf(r,balanceOf_x1_0),paused(b),b!=true,recv_transferFrom(o,r,s,n),totalSupply(totalSupply_n_1).
pause() :- recv_pause().
```

### Original concrete final DL transaction rules

```prolog
decreaseAllowance(o,s,n) :- recv_decreaseAllowance(o,s,n),allowance(o,s,allowance_x2),n<=allowance_x2.
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
increaseAllowance(o,s,n) :- recv_increaseAllowance(o,s,n),n>0.
pause() :- recv_pause().
transferFrom(o,r,s,n) :- n>0,allowance(o,s,allowance_x2_1),paused(b),b!=true,n<allowance_x2_1,balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n<balanceOf_x1_2.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),paused(b),b!=true,n<balanceOf_x1_1,n>=0.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
unpause() :- recv_unpause().
```

## tether

- Symbolic result: `success`, time `653.097`, iterations `27`, timeout run `900s`.
- Note: Symbolic transferFrom checks recipient balance and n >= totalSupply; original concrete checks allowance and owner balance.

### Fixed symbolic final DL transaction rules

```prolog
destroyBlackFund(p,n) :- recv_destroyBlackFund(p,n).
transferFrom(o,r,s,n) :- n<balanceOf_x1_1,recv_transferFrom(o,r,s,n),balanceOf(r,balanceOf_x1_1),n>=totalSupply_n_2,n>0,totalSupply(totalSupply_n_2).
addBlackList(p) :- recv_addBlackList(p),owner(o),msgSender(s),o==s.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
issue(p,n) :- msgSender(s),recv_issue(p,n),o==s,owner(o),n>=0.
redeem(p,n) :- recv_redeem(p,n),balanceOf(p,balanceOf_x1),n<=balanceOf_x1.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>=0,n<=balanceOf_x1_1.
```

### Original concrete final DL transaction rules

```prolog
destroyBlackFund(p,n) :- recv_destroyBlackFund(p,n).
addBlackList(p) :- recv_addBlackList(p),owner(o),msgSender(s),o==s.
transferFrom(o,r,s,n) :- allowance(o,s,allowance_x2_1),balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n<=balanceOf_x1_2,n<=allowance_x2_1,n>=0.
issue(p,n) :- msgSender(s),n>0,recv_issue(p,n),o==s,owner(o).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
redeem(p,n) :- recv_redeem(p,n),balanceOf(p,balanceOf_x1),n<=balanceOf_x1.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>0.
```

## wbtc

- Symbolic result: `success`, time `455.635`, iterations `33`, timeout run `900s`.
- Note: Both have suspicious claimOwnership pendingOwner != p; symbolic additionally has totalSupply == 0 transferFrom.

### Fixed symbolic final DL transaction rules

```prolog
claimOwnership(p) :- recv_claimOwnership(p),pendingOwner(s_1),p!=address(0),s_1!=p.
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- 0!=balanceOf_x1_0,totalSupply(totalSupply_n_1),0==totalSupply_n_1,recv_transferFrom(o,r,s,n),balanceOf(s,balanceOf_x1_0).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
transferOwnership(p) :- o_1==s_1,p!=address(0),msgSender(s_1),owner(o_1),recv_transferOwnership(p).
paused(false) :- o_1==s_1,msgSender(s_1),b_0!=false,owner(o_1),recv_unpause(),paused(b_0).
paused(true) :- o_1==s_1,recv_pause(),msgSender(s_1),b_0!=true,paused(b_0),owner(o_1).
increaseApproval(o,s,n) :- recv_increaseApproval(o,s,n),n>=0.
decreaseApproval(o,s,n) :- recv_decreaseApproval(o,s,n),allowance(o,s,allowance_x2),n<allowance_x2.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
```

### Original concrete final DL transaction rules

```prolog
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferOwnership(p) :- o_1==s_1,p!=address(0),msgSender(s_1),owner(o_1),recv_transferOwnership(p).
paused(false) :- o_1==s_1,msgSender(s_1),b_0!=false,owner(o_1),recv_unpause(),paused(b_0).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>=0,n<balanceOf_x1_1.
paused(true) :- o_1==s_1,recv_pause(),msgSender(s_1),b_0!=true,paused(b_0),owner(o_1).
increaseApproval(o,s,n) :- recv_increaseApproval(o,s,n),n>=0.
claimOwnership(p) :- recv_claimOwnership(p),pendingOwner(s_1),p!=address(0),s_1!=p.
transferFrom(o,r,s,n) :- n>0,allowance(o,s,allowance_x2_1),n<allowance_x2_1,balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n<=balanceOf_x1_2.
decreaseApproval(o,s,n) :- recv_decreaseApproval(o,s,n),allowance(o,s,allowance_x2),n<allowance_x2.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
```

## ltcSwapAsset

- Symbolic result: `success`, time `8.605`, iterations `1`, timeout run `300s`.
- Note: Original concrete is already suspicious/over-strong, but symbolic adds n > totalSupply to transferFrom.

### Fixed symbolic final DL transaction rules

```prolog
burn(p,n) :- o_1==s_1,n>0,balanceOf(p,b_2),msgSender(s_1),n<=b_2,owner(o_1),recv_burn(p,n).
transferFrom(o,r,s,n) :- n>0,n<=a_2,n<=b_1,totalSupply(totalSupply_n),balanceOf(s,b_1),allowance(s,o,a_2),recv_transferFrom(o,r,s,n),n>totalSupply_n.
swapOwnerTx(p,q,d) :- o_1==s_1,recv_swapOwnerTx(p,q,d),msgSender(s_1),owner(o_1),d>0.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>0.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,b_1),n>0,n<=b_1.
mint(p,n) :- o_1==s_1,n>0,recv_mint(p,n),msgSender(s_1),owner(o_1).
```

### Original concrete final DL transaction rules

```prolog
burn(p,n) :- o_1==s_1,n>0,balanceOf(p,b_2),msgSender(s_1),n<=b_2,owner(o_1),recv_burn(p,n).
swapOwnerTx(p,q,d) :- o_1==s_1,recv_swapOwnerTx(p,q,d),msgSender(s_1),owner(o_1),d>0.
transferFrom(o,r,s,n) :- n>0,n<=a_2,n<=b_1,balanceOf(s,b_1),allowance(s,o,a_2),recv_transferFrom(o,r,s,n).
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),allowance(s,o,allowance_x2),d>0,d<=allowance_x2.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,b_1),n>0,n<=b_1.
mint(p,n) :- o_1==s_1,n>0,recv_mint(p,n),msgSender(s_1),owner(o_1).
```

## cappedCrowdSale

- Symbolic result: `success`, time `1111.926`, iterations `38`, timeout run `1200s`.
- Note: Original concrete has impossible finalize totalSupply < 0; symbolic also has bad finalize and transferFrom.

### Fixed symbolic final DL transaction rules

```prolog
finalize() :- msgSender(msgSender),balanceOf(msgSender,balanceOf_x1_0),balanceOf_x1_0>0,totalSupply(totalSupply_n_1),0==totalSupply_n_1,recv_finalize().
burn(p,n) :- msgSender(s),n<balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
buyToken(p,m) :- recv_buyToken(p,m),m>0,p!=address(0).
transferFrom(o,r,s,n) :- n<balanceOf_x1_0,balanceOf(r,balanceOf_x1_0),n>=totalSupply_n_1,recv_transferFrom(o,r,s,n),totalSupply(totalSupply_n_1).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>=0,n<balanceOf_x1_1.
```

### Original concrete final DL transaction rules

```prolog
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<balanceOf_x1_1.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- n>0,allowance(o,s,allowance_x2_1),balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n<=allowance_x2_1,n<balanceOf_x1_2.
finalize() :- recv_finalize(),totalSupply(totalSupply_n),totalSupply_n<0.
buyToken(p,m) :- recv_buyToken(p,m),m>0,p!=address(0).
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
```

## auction

- Symbolic result: `success`, time `1.386`, iterations `1`, timeout run `300s`.
- Note: Both concrete and symbolic have the same contradictory withdraw guard.

### Fixed symbolic final DL transaction rules

```prolog
endAuction() :- b_1!=true,recv_endAuction(),owner(o_0),o_0==s_0,auctionEnded(b_1),msgSender(s_0).
bid(p,n) :- auctionEnded(b_0),highestBid(m_1),n>m_1,recv_bid(p,n),b_0!=true.
withdraw(p,n) :- auctionEnded_b==false,b==true,auctionEnded(b),auctionEnded(auctionEnded_b),recv_withdraw(p,n).
```

### Original concrete final DL transaction rules

```prolog
endAuction() :- b_1!=true,recv_endAuction(),owner(o_0),o_0==s_0,auctionEnded(b_1),msgSender(s_0).
bid(p,n) :- auctionEnded(b_0),highestBid(m_1),n>m_1,recv_bid(p,n),b_0!=true.
withdraw(p,n) :- auctionEnded_b==false,b==true,auctionEnded(b),auctionEnded(auctionEnded_b),recv_withdraw(p,n).
```

## crowFunding

- Symbolic result: `success`, time `4.238`, iterations `3`, timeout run `300s`.
- Note: Symbolic refund has closed true/false contradiction; original concrete refund does not.

### Fixed symbolic final DL transaction rules

```prolog
refund(p,n) :- recv_refund(p,n),closed(b_0),closed(closed_b),target(t_1),raised(r_1),b_0!=false,closed_b==false,r_1<t_1.
invest(p,n) :- recv_invest(p,n),n>=0.
close() :- recv_close(),owner(o),msgSender(s),o==s.
withdraw(p,r) :- beneficiary(b_1),recv_withdraw(p,r),r_p_0>=t_0,p==b_1,target(t_0),raised(r_p_0).
```

### Original concrete final DL transaction rules

```prolog
refund(p,n) :- recv_refund(p,n),closed(b_0),target(t_1),n<balanceOf_x1,balanceOf(p,balanceOf_x1),r_1<t_1,raised(r_1),b_0!=false.
invest(p,n) :- recv_invest(p,n),closed(closed_b_1),n>=0,closed_b_1==false.
close() :- recv_close(),owner(o),msgSender(s),o==s.
withdraw(p,r) :- beneficiary(b_1),recv_withdraw(p,r),r_p_0>=t_0,p==b_1,target(t_0),raised(r_p_0).
```

## finalizableCrowdSale

- Symbolic result: `success`, time `585.163`, iterations `29`, timeout run `900s`.
- Note: Symbolic transferFrom is bad; original concrete finalize and transferFrom are reasonable.

### Fixed symbolic final DL transaction rules

```prolog
burn(p,n) :- msgSender(s),n<balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
finalize() :- recv_finalize(),owner(o),msgSender(s),o==s.
transferFrom(o,r,s,n) :- n<balanceOf_x1_0,balanceOf(r,balanceOf_x1_0),n>=totalSupply_n_1,recv_transferFrom(o,r,s,n),totalSupply(totalSupply_n_1).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>=0,n<balanceOf_x1_1.
buyToken(p,m) :- recv_buyToken(p,m),m>0.
```

### Original concrete final DL transaction rules

```prolog
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- allowance(o,s,allowance_x2_1),n<allowance_x2_1,balanceOf(o,balanceOf_x1_2),recv_transferFrom(o,r,s,n),n>=0,n<balanceOf_x1_2.
finalize() :- recv_finalize(),owner(o),msgSender(s),o==s.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>0.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),o==s,owner(o),recv_burn(p,n).
buyToken(p,m) :- recv_buyToken(p,m),m>0.
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
```

## nft

- Symbolic result: `success`, time `11.545`, iterations `7`, timeout run `300s`.
- Note: Symbolic mint requires tokenId <= 0 and totalMinted > 0; original concrete mint is redundant but not obviously wrong.

### Fixed symbolic final DL transaction rules

```prolog
mint(to,tokenId) :- msgSender(s),tokenId<=0,totalMinted_n_1>0,totalMinted(totalMinted_n_1),o==s,owner(o),recv_mint(to,tokenId).
transferFrom(from,to,tokenId) :- recv_transferFrom(from,to,tokenId),approved(tokenId,a),msgSender(s),a==s.
approve(o,spender,tokenId) :- recv_approve(spender,tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
burn(tokenId) :- recv_burn(tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
transfer(from,to,tokenId) :- recv_transfer(from,to,tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
```

### Original concrete final DL transaction rules

```prolog
transferFrom(from,to,tokenId) :- recv_transferFrom(from,to,tokenId),approved(tokenId,a),msgSender(s),a==s.
mint(to,tokenId) :- msgSender(s),owner(owner_x),o==s,owner(o),msgSender(msgSender_x),owner_x==msgSender_x,recv_mint(to,tokenId).
approve(o,spender,tokenId) :- recv_approve(spender,tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
burn(tokenId) :- recv_burn(tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
transfer(from,to,tokenId) :- recv_transfer(from,to,tokenId),ownerOf(tokenId,o),msgSender(s),o==s.
```

## erc20burnable

- Symbolic result: `success`, time `230.261`, iterations `31`, timeout run `300s`.
- Note: Original concrete burnFrom is already suspicious; symbolic burnFrom is more clearly impossible with totalSupply <= 0.

### Fixed symbolic final DL transaction rules

```prolog
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),p==s,recv_burn(p,n).
burnFrom(from,s,n) :- n>0,msgSender(s_p_1),recv_burnFrom(from,s,n),s==s_p_1,totalSupply_n_1<=0,balanceOf_x1_0>0,balanceOf(s,balanceOf_x1_0),totalSupply(totalSupply_n_1).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
transferFrom(o,r,s,n) :- recv_transferFrom(o,r,s,n),allowance(o,s,allowance_x2),n<=allowance_x2.
```

### Original concrete final DL transaction rules

```prolog
increaseAllowance(o,s,d) :- recv_increaseAllowance(o,s,d),d>=0.
mint(p,n) :- msgSender(s),recv_mint(p,n),o==s,owner(o),n>=0.
transferFrom(o,r,s,n) :- recv_transferFrom(o,r,s,n),allowance(o,s,allowance_x2),n<allowance_x2.
burnFrom(from,s,n) :- n<=allowance_x2_0,msgSender(s_p_1),s==s_p_1,allowance(msgSender,from,allowance_x2_1),0==allowance_x2_1,allowance(s,from,allowance_x2_0),n>0,msgSender(msgSender),recv_burnFrom(from,s,n).
burn(p,n) :- msgSender(s),n<=balanceOf_x1,balanceOf(p,balanceOf_x1),p==s,recv_burn(p,n).
transfer(s,r,n) :- recv_transfer(s,r,n),balanceOf(s,balanceOf_x1_1),n>0,n<=balanceOf_x1_1.
```

