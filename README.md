# yETH-bootstrap
Implementation of bootstrap phase as outlined in [YIP-72](https://gov.yearn.finance/t/yip-72-launch-yeth/13158).

### Install dependencies
```sh
# Install foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup
# Install ape
pip install eth-ape
# Install required ape plugins
ape plugins install .
```

### Run tests
```sh
ape test
ape test tests/pol_curve_lp.py --network ethereum:mainnet-fork
```
