//@ts-nocheck

import { ApiPromise, Keyring, WsProvider } from "@polkadot/api";

import Web3 from "web3";

async function main() {

	const substrateApi = await ApiPromise.create({
		provider: new WsProvider("ws://127.0.0.1:56054"),
		types: {
			Balance: "u128",
			Address: "AccountId",
			LookupSource: "AccountId",
			Account: {
				nonce: "U256",
				balance: "U256",
			}
		},
	});
	const keyring = new Keyring({ss58Format: 0});
	const geraldKeyPair = keyring.addFromUri("wash pass sweet crawl purse expire carbon amazing mosquito turtle affair danger");
    let nonce = await substrateApi.rpc.system.accountNextIndex(geraldKeyPair.address);

    while(true) {
        let substrateAccount = await substrateApi.query.system.account(geraldKeyPair.address);
        console.log(`\nBalance for ${geraldKeyPair.address} on Substrate: ${substrateAccount.data.free.toString()}`);
        
        const glmrCount = "1000000000000000000";
        //const nonce = await substrateApi.rpc.system.accountNextIndex("12n4umkT22aSWUEforpPtMdcFDgLurp7JP61PttBm5P2xnU7");
        const unsub = await substrateApi.tx.balances
        .transfer("0x1111111111111111111111111111111111111111", glmrCount)
        .signAndSend(geraldKeyPair, { nonce }, (result) => {
                if (result.status.isInBlock) {
                    console.log(`Payment included at blockHash ${result.status.asInBlock} (waiting finalization...)`);
                    unsub();
                }
            });
        await new Promise(resolve => {
            setTimeout(resolve, 4000);
        })
        nonce++;
    }
}


main()
	.catch(console.error)
	.finally(() => process.exit());