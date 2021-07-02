// Copyright 2019-2020 PureStake Inc.
// This file is part of Moonbeam.

// Moonbeam is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// Moonbeam is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with Moonbeam.  If not, see <http://www.gnu.org/licenses/>.

//! # Migrations

use frame_support::{pallet_prelude::Get, weights::Weight};
use pallet_migrations::Migration;
use sp_runtime::Perbill;
use sp_std::{
	marker::PhantomData,
	prelude::*,
};

use parachain_staking::Call;

/// This module acts as a registry where each migration is defined. Each migration should implement
/// the "Migration" trait declared in the pallet-migrations crate.

#[allow(non_camel_case_types)]
pub struct MM_001_AuthorMappingAddDeposit;
impl Migration for MM_001_AuthorMappingAddDeposit {
	fn friendly_name(&self) -> &str {
		"AuthorMappingAddDeposit"
	}
	fn step(&self, _previous_progress: Perbill, _available_weight: Weight) -> (Perbill, Weight) {
		// reviewer note: this isn't meant to imply that migration code must live here. As noted
		// elsewhere, I would expect migration code to live close to the pallet it affects.
		(Perbill::one(), 0u64.into())
	}
}

#[allow(non_camel_case_types)]
pub struct MM_002_StakingFixTotalBalance;
impl Migration for MM_002_StakingFixTotalBalance {
	fn friendly_name(&self) -> &str {
		"StakingFixTotalBalance"
	}
	fn step(&self, _previous_progress: Perbill, _available_weight: Weight) -> (Perbill, Weight) {
		(Perbill::one(), 0u64.into())
	}
}

#[allow(non_camel_case_types)]
pub struct MM_003_StakingUnboundedCollatorNominations<Runtime>(PhantomData<Runtime>);
impl<Runtime> Migration for MM_003_StakingUnboundedCollatorNominations<Runtime>
where
	Runtime: parachain_staking::Config
{
	fn friendly_name(&self) -> &str {
		"StakingUnboundedCollatorNominations"
	}
	fn step(&self, _previous_progress: Perbill, _available_weight: Weight) -> (Perbill, Weight) {
		parachain_staking::Call::<Runtime>::go_offline();
		(Perbill::one(), 0u64.into())
	}
}

pub struct CommonMigrations<Runtime>(PhantomData<Runtime>);
impl<Runtime> Get<Vec<Box<dyn Migration>>> for CommonMigrations<Runtime>
where
	Runtime: parachain_staking::Config
{
	fn get() -> Vec<Box<dyn Migration>> {
		let test = MM_003_StakingUnboundedCollatorNominations::<Runtime> {0: Default::default()};
		// TODO: this is a lot of allocation to do upon every get() call. this *should* be avoided
		// except when pallet_migrations undergoes a runtime upgrade -- but TODO: review
		vec![
			Box::new(MM_001_AuthorMappingAddDeposit),
			Box::new(MM_002_StakingFixTotalBalance),
			Box::new(test),
		]
	}
}
