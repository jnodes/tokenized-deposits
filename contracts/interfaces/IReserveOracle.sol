// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/**
 * @title IReserveOracle
 * @notice Interface for the 1:1 reserve backing oracle used by M&T Bank's Cari Deposit
 *         Account (CDA) platform on the Cari Network / ZKsync Prividium.
 *
 *         This oracle ensures every CDA token is backed 1:1 by qualifying reserves
 *         per GENIUS Act Section 4 (cash, T-bills, Fed deposits).
 *
 * @dev    Implementations may wrap Chainlink data feeds, Prividium-native zk-proof attestations,
 *         or an off-chain reserve proof service. The CDA contract queries this oracle before
 *         every mint to enforce GENIUS Act Section 4 (1:1 reserve backing).
 *
 *         SECURITY GUARDIAN NOTE: The oracle updater key MUST be stored in an HSM
 *         (Thales Luna / Utimaco) with dual-control key ceremony. Updates should be
 *         gated by M&T Bank treasury operations with separation of duties (SoD)
 *         between the attestor and the minter.
 */
interface IReserveOracle {
    /// @notice Emitted when the reserve attestation is updated.
    /// @param totalReserves   Total qualifying reserves (6-decimal USD value).
    /// @param attestedAt      Block timestamp of the attestation.
    /// @param attestationHash IPFS/Arweave hash of the signed reserve report.
    event ReserveAttestationUpdated(
        uint256 totalReserves,
        uint256 attestedAt,
        bytes32 attestationHash
    );

    /// @notice Emitted when attestation is approaching staleness (past warning threshold)
    /// @param lastAttestedAt    Block timestamp of the last attestation.
    /// @param maxStaleness      Maximum allowed staleness in seconds.
    /// @param currentTimestamp  Current block timestamp.
    event AttestationStalenessWarning(
        uint256 lastAttestedAt,
        uint256 maxStaleness,
        uint256 currentTimestamp
    );

    /// @notice Emitted when attestation becomes stale
    /// @param lastAttestedAt    Block timestamp of the last attestation.
    /// @param maxStaleness      Maximum allowed staleness in seconds.
    /// @param currentTimestamp  Current block timestamp.
    event AttestationStale(
        uint256 lastAttestedAt,
        uint256 maxStaleness,
        uint256 currentTimestamp
    );

    /// @notice Returns the most recent attested total reserves backing CDA supply (6-decimal USD).
    function totalReserves() external view returns (uint256);

    /// @notice Returns the block timestamp of the last attestation.
    function lastAttestedAt() external view returns (uint256);

    /// @notice Returns the hash of the most recent signed reserve report.
    function attestationHash() external view returns (bytes32);

    /// @notice Check whether minting `amount` CDA would violate the 1:1 backing invariant.
    /// @param currentSupply Current total supply of the CDA.
    /// @param mintAmount    Amount of CDA to be minted (6 decimals).
    /// @return True if (currentSupply + mintAmount) <= totalReserves.
    function canMint(uint256 currentSupply, uint256 mintAmount) external view returns (bool);

    /// @notice Submit a new reserve attestation.
    /// @param _totalReserves   Attested total qualifying reserves (6-decimal USD).
    /// @param _attestationHash Hash of the signed reserve report document.
    function updateAttestation(uint256 _totalReserves, bytes32 _attestationHash) external;

    /// @notice Check attestation freshness and emit warning events if approaching staleness.
    /// @dev    Callable by anyone (no role restriction) so monitoring systems can call it.
    /// @return isFresh          True if attestation is not stale.
    /// @return secondsUntilStale Seconds remaining until attestation becomes stale (0 if already stale).
    function checkStaleness() external returns (bool isFresh, uint256 secondsUntilStale);
}
