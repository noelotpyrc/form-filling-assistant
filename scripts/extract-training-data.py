#!/usr/bin/env python3
"""
Extract atomic training data from simulation JSONL logs.

Produces one JSONL file where each line is a single LLM A turn with full context:
- system_prompt (reconstructed or length)
- user_message
- assistant_output (raw_text)
- form_state_before / form_state_after
- conversation_history (all prior turns)
- metadata (persona, profile, turn, session, actions, etc.)

This atomic format can be converted to any training format (SFT, DPO, GRPO) downstream.

Usage:
  python3 scripts/extract-training-data.py sims/sim-northfield-*.jsonl
  python3 scripts/extract-training-data.py sims/ --output training-data/atomic.jsonl
  python3 scripts/extract-training-data.py sims/ --stats  # just print stats, no output
"""

import json
import os
import sys
import glob
import argparse
from pathlib import Path


def parse_session(filepath: str) -> list[dict]:
    """Parse a session JSONL file into a list of entries."""
    entries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def extract_atomic_turns(filepath: str) -> list[dict]:
    """Extract atomic LLM A turn data from a session log."""
    entries = parse_session(filepath)
    session_id = Path(filepath).stem  # filename without extension

    # Find state_init
    state_init = next((e for e in entries if e['type'] == 'state_init'), None)
    if not state_init:
        return []

    persona = state_init.get('persona', '')
    profile = state_init.get('profile', '')
    form_id = state_init.get('form_id', '')
    form_name = state_init.get('form_name', '')
    config = state_init.get('session_config', {})
    split_prompt = config.get('splitPrompt', False)

    # Find session_end
    session_end = next((e for e in entries if e['type'] == 'session_end'), None)
    end_reason = session_end.get('reason', 'unknown') if session_end else 'unknown'

    # Build ordered list of llm_a_input + llm_a_output pairs
    a_inputs = [e for e in entries if e['type'] == 'llm_a_input']
    a_outputs = [e for e in entries if e['type'] == 'llm_a_output']
    state_updates = [e for e in entries if e['type'] == 'state_update']

    # Index state_updates by turn for form_state_before/after
    # form_state_before for turn N = form_values from the last state_update before this turn
    # form_state_after for turn N = form_values from state_update(s) at this turn with source=llm_a

    # Build a map: turn -> form_state snapshots
    state_by_turn: dict[int, dict] = {}
    for su in state_updates:
        turn = su.get('turn', -1)
        if turn not in state_by_turn:
            state_by_turn[turn] = {'before': None, 'after': None}
        # The last state_update at this turn is the "after" state
        state_by_turn[turn]['after'] = su.get('form_values', {})

    # Conversation history accumulator
    conversation: list[dict] = []
    atomic_turns: list[dict] = []

    # Match inputs to outputs by turn number
    output_by_turn = {e['turn']: e for e in a_outputs}
    input_by_turn = {e['turn']: e for e in a_inputs}

    # Get all turns that have an output
    turns_with_output = sorted(output_by_turn.keys())

    # Track form state progression
    current_form_state = dict(state_init.get('initial_form_values', {}))

    for turn in turns_with_output:
        a_input = input_by_turn.get(turn)
        a_output = output_by_turn[turn]

        if not a_input:
            continue

        user_message = a_input.get('user_message', '')
        raw_text = a_output.get('raw_text', '')
        parsed_actions = a_output.get('parsed_actions', [])

        # Determine form state before this turn
        form_state_before = dict(current_form_state)

        # Determine form state after (from state_updates at this turn)
        form_state_after = form_state_before
        for su in state_updates:
            if su.get('turn') == turn and su.get('source') == 'llm_a':
                form_state_after = dict(su.get('form_values', form_state_before))

        # Derive metadata
        has_actions = '---actions---' in (raw_text or '')
        action_types = list(set(a.get('type', '') for a in parsed_actions)) if parsed_actions else []

        # Build atomic record
        record = {
            # Core training pair
            'user_message': user_message,
            'assistant_output': raw_text,

            # Context
            'system_prompt_length': a_input.get('system_prompt_length', 0),
            'form_state_before': form_state_before,
            'form_state_after': form_state_after,
            'conversation_history': list(conversation),  # copy

            # Structured output
            'parsed_actions': parsed_actions,
            'has_actions': has_actions,
            'action_types': action_types,

            # Metadata
            'turn': turn,
            'session_id': session_id,
            'persona': persona,
            'profile': profile,
            'form_id': form_id,
            'form_name': form_name,
            'split_prompt': split_prompt,
            'end_reason': end_reason,
            'cost_usd': a_output.get('cost_usd', 0),
            'duration_ms': a_output.get('duration_ms', 0),
        }

        atomic_turns.append(record)

        # Update conversation history for next turn
        conversation.append({
            'role': 'user',
            'content': user_message,
        })
        conversation.append({
            'role': 'assistant',
            'content': raw_text,
        })

        # Update current form state
        # Apply all state_updates at this turn (any source)
        for su in state_updates:
            if su.get('turn') == turn:
                current_form_state = dict(su.get('form_values', current_form_state))

    return atomic_turns


def print_stats(all_turns: list[dict]):
    """Print summary statistics."""
    sessions = set(t['session_id'] for t in all_turns)
    with_actions = [t for t in all_turns if t['has_actions']]
    text_only = [t for t in all_turns if not t['has_actions']]

    print(f'Sessions: {len(sessions)}')
    print(f'Total LLM A turns: {len(all_turns)}')
    print(f'  With actions: {len(with_actions)} ({len(with_actions)*100//len(all_turns)}%)')
    print(f'  Text-only: {len(text_only)} ({len(text_only)*100//len(all_turns)}%)')
    print()

    # Action type distribution
    action_counts: dict[str, int] = {}
    for t in with_actions:
        for at in t['action_types']:
            action_counts[at] = action_counts.get(at, 0) + 1
    print('Action type distribution:')
    for at, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        print(f'  {at}: {count}')
    print()

    # By profile
    profiles: dict[str, dict] = {}
    for t in all_turns:
        p = t['profile']
        if p not in profiles:
            profiles[p] = {'total': 0, 'with_actions': 0}
        profiles[p]['total'] += 1
        if t['has_actions']:
            profiles[p]['with_actions'] += 1

    print('By profile:')
    for p in sorted(profiles):
        d = profiles[p]
        pct = d['with_actions'] * 100 // d['total'] if d['total'] else 0
        print(f'  {p:12s}: {d["total"]:3d} turns, {d["with_actions"]:3d} with actions ({pct}%)')
    print()

    # By persona
    personas: dict[str, int] = {}
    for t in all_turns:
        personas[t['persona']] = personas.get(t['persona'], 0) + 1
    print('By persona:')
    for p in sorted(personas):
        print(f'  {p}: {personas[p]} turns')
    print()

    # Conversation length distribution
    hist_lens = [len(t['conversation_history']) // 2 for t in all_turns]  # pairs
    print(f'Conversation history depth:')
    print(f'  Turn 0 (no history): {hist_lens.count(0)}')
    print(f'  1-5 prior turns: {sum(1 for x in hist_lens if 1 <= x <= 5)}')
    print(f'  6-15 prior turns: {sum(1 for x in hist_lens if 6 <= x <= 15)}')
    print(f'  16+ prior turns: {sum(1 for x in hist_lens if x >= 16)}')


def main():
    parser = argparse.ArgumentParser(description='Extract atomic training data from simulation logs')
    parser.add_argument('inputs', nargs='+', help='JSONL files or directories')
    parser.add_argument('--output', '-o', default='sims/training-data-atomic.jsonl',
                        help='Output JSONL file (default: sims/training-data-atomic.jsonl)')
    parser.add_argument('--stats', action='store_true', help='Print stats only, no output file')
    args = parser.parse_args()

    # Collect input files
    files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            files.extend(sorted(glob.glob(os.path.join(inp, 'sim-*.jsonl'))))
        elif '*' in inp:
            files.extend(sorted(glob.glob(inp)))
        else:
            files.append(inp)

    if not files:
        print('No input files found.', file=sys.stderr)
        sys.exit(1)

    print(f'Processing {len(files)} session files...')

    # Extract all turns
    all_turns = []
    for f in files:
        turns = extract_atomic_turns(f)
        all_turns.extend(turns)

    print(f'Extracted {len(all_turns)} atomic turns')
    print()

    # Stats
    print_stats(all_turns)

    # Write output
    if not args.stats:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w') as out:
            for t in all_turns:
                out.write(json.dumps(t, ensure_ascii=False) + '\n')
        print(f'Written to: {args.output}')
        # File size
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f'File size: {size_mb:.1f} MB')


if __name__ == '__main__':
    main()
