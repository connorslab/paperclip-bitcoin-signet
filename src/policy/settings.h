// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_POLICY_SETTINGS_H
#define BITCOIN_POLICY_SETTINGS_H

#include <optional>

extern unsigned int g_script_size_policy_limit;
inline constexpr unsigned int DEFAULT_CSFS_MESSAGE_SIZE_LIMIT{32};
extern std::optional<unsigned int> g_csfs_message_size_limit;
extern unsigned int nBytesPerSigOp;
extern unsigned int nBytesPerSigOpStrict;
extern unsigned int g_weight_per_data_byte;

#endif // BITCOIN_POLICY_SETTINGS_H
