// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./TestHelper.sol";

/**
 * @title FuzzTest
 * @notice Fuzz tests for MTokenizedDeposit and ReserveOracle.
 *         Validates 1:1 backing invariant, role enforcement, and compliance under random inputs.
 *         M&T Bank | Cari Network | ZKsync Prividium.
 */
contract FuzzTest is TestHelper {
    // =========================================================================
    //                  FUZZ: RESERVE BACKING (GENIUS Act S4)
    // =========================================================================

    /// @dev Minting any amount within reserves should succeed.
    function testFuzz_mint_withinReserves(uint256 amount) public {
        amount = bound(amount, 1, INITIAL_RESERVES);

        vm.prank(minter);
        token.mint(alice, amount, "fuzz-ref");

        assertEq(token.balanceOf(alice), amount);
        assertLe(token.totalSupply(), oracle.totalReserves());
    }

    /// @dev Minting above reserves must revert.
    function testFuzz_mint_aboveReserves_reverts(uint256 amount) public {
        amount = bound(amount, INITIAL_RESERVES + 1, type(uint128).max);

        vm.prank(minter);
        vm.expectRevert();
        token.mint(alice, amount, "fuzz-ref");
    }

    /// @dev Mint then burn: supply stays consistent.
    function testFuzz_mintThenBurn_supplyConsistent(uint256 mintAmt, uint256 burnAmt) public {
        mintAmt = bound(mintAmt, 1, INITIAL_RESERVES);
        burnAmt = bound(burnAmt, 1, mintAmt);

        vm.prank(minter);
        token.mint(alice, mintAmt, "fuzz-mint");

        vm.prank(burner);
        token.burn(alice, burnAmt, "fuzz-burn");

        assertEq(token.totalSupply(), mintAmt - burnAmt);
        assertEq(token.balanceOf(alice), mintAmt - burnAmt);
    }

    // =========================================================================
    //                  FUZZ: TRANSFER COMPLIANCE
    // =========================================================================

    /// @dev Transfers between whitelisted, non-frozen accounts should succeed.
    function testFuzz_transfer_whitelisted(uint256 amount) public {
        uint256 mintAmt = bound(amount, 1, INITIAL_RESERVES);
        _mint(alice, mintAmt);

        uint256 xferAmt = bound(amount, 1, mintAmt);

        vm.prank(alice);
        token.transfer(bob, xferAmt);

        assertEq(token.balanceOf(alice), mintAmt - xferAmt);
        assertEq(token.balanceOf(bob), xferAmt);
    }

    // =========================================================================
    //                  FUZZ: RESERVE ORACLE ATTESTATION
    // =========================================================================

    /// @dev Any positive reserve amount should be accepted.
    function testFuzz_updateAttestation(uint256 reserves) public {
        reserves = bound(reserves, 1, type(uint128).max);
        bytes32 hash = keccak256(abi.encodePacked(reserves));

        vm.prank(attestor);
        oracle.updateAttestation(reserves, hash);

        assertEq(oracle.totalReserves(), reserves);
        assertEq(oracle.attestationHash(), hash);
    }

    /// @dev canMint should return true iff supply + mint <= reserves.
    function testFuzz_canMint_logic(uint256 supply, uint256 mintAmt, uint256 reserves) public {
        supply = bound(supply, 0, type(uint128).max);
        mintAmt = bound(mintAmt, 0, type(uint128).max);
        reserves = bound(reserves, 1, type(uint128).max);

        vm.prank(attestor);
        oracle.updateAttestation(reserves, keccak256("fuzz"));

        bool result = oracle.canMint(supply, mintAmt);
        bool expected = (supply + mintAmt) <= reserves;

        assertEq(result, expected);
    }

    // =========================================================================
    //                  FUZZ: STALENESS
    // =========================================================================

    /// @dev Staleness check should correctly transition.
    function testFuzz_staleness_transition(uint256 warpSeconds) public {
        warpSeconds = bound(warpSeconds, 0, MAX_STALENESS * 3);

        vm.warp(block.timestamp + warpSeconds);

        bool expected = warpSeconds <= MAX_STALENESS;
        assertEq(oracle.isAttestationFresh(), expected);
    }
}

/**
 * @title InvariantTest
 * @notice Invariant tests ensuring the 1:1 backing constraint is never violated
 *         across arbitrary sequences of mint/burn/transfer operations.
 *         M&T Bank | Cari Network | ZKsync Prividium.
 */
contract InvariantHandler is TestHelper {
    uint256 public ghost_totalMinted;
    uint256 public ghost_totalBurned;

    function setUp() public override {
        super.setUp();
    }

    function handler_mint(uint256 amount) external {
        amount = bound(amount, 1, 100_000e6);

        // Ensure reserves can cover it
        if (token.totalSupply() + amount > oracle.totalReserves()) return;

        vm.prank(minter);
        token.mint(alice, amount, "inv-mint");
        ghost_totalMinted += amount;
    }

    function handler_burn(uint256 amount) external {
        uint256 balance = token.balanceOf(alice);
        if (balance == 0) return;
        amount = bound(amount, 1, balance);

        vm.prank(burner);
        token.burn(alice, amount, "inv-burn");
        ghost_totalBurned += amount;
    }

    function handler_transfer(uint256 amount) external {
        uint256 balance = token.balanceOf(alice);
        if (balance == 0) return;
        amount = bound(amount, 1, balance);

        vm.prank(alice);
        token.transfer(bob, amount);
    }
}

contract InvariantTest is Test {
    InvariantHandler public handler;

    function setUp() public {
        handler = new InvariantHandler();
        handler.setUp();

        targetContract(address(handler));

        // Only target our handler functions
        bytes4[] memory selectors = new bytes4[](3);
        selectors[0] = InvariantHandler.handler_mint.selector;
        selectors[1] = InvariantHandler.handler_burn.selector;
        selectors[2] = InvariantHandler.handler_transfer.selector;
        targetSelector(FuzzSelector({addr: address(handler), selectors: selectors}));
    }

    /// @dev CRITICAL INVARIANT: totalSupply <= totalReserves (1:1 backing).
    function invariant_supplyNeverExceedsReserves() public view {
        assertLe(
            handler.token().totalSupply(),
            handler.oracle().totalReserves(),
            "INVARIANT VIOLATED: totalSupply > totalReserves (1:1 backing broken)"
        );
    }

    /// @dev Supply must equal minted - burned.
    function invariant_supplyEqualsMintedMinusBurned() public view {
        assertEq(
            handler.token().totalSupply(),
            handler.ghost_totalMinted() - handler.ghost_totalBurned(),
            "INVARIANT VIOLATED: supply != minted - burned"
        );
    }
}
