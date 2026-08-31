from pmigrate.graph.toposort import strongly_connected_components, topo_batches


def _index_of(batches: list[list[str]], node: str) -> int:
    for i, batch in enumerate(batches):
        if node in batch:
            return i
    raise AssertionError(f"{node} not found in {batches}")


def test_linear_chain_is_leaf_first() -> None:
    # A imports B imports C -> migrate C, then B, then A
    nodes = {"A", "B", "C"}
    edges = [("A", "B"), ("B", "C")]
    batches = topo_batches(nodes, edges)
    assert _index_of(batches, "C") < _index_of(batches, "B") < _index_of(batches, "A")


def test_diamond_dependency() -> None:
    # A imports B and C; both B and C import D -> D first, A last, B/C in between (either order)
    nodes = {"A", "B", "C", "D"}
    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
    batches = topo_batches(nodes, edges)
    assert _index_of(batches, "D") < _index_of(batches, "B")
    assert _index_of(batches, "D") < _index_of(batches, "C")
    assert _index_of(batches, "B") < _index_of(batches, "A")
    assert _index_of(batches, "C") < _index_of(batches, "A")


def test_mutual_cycle_forms_one_batch() -> None:
    nodes = {"A", "B", "C"}
    edges = [("A", "B"), ("B", "A"), ("B", "C")]
    sccs = strongly_connected_components(nodes, edges)
    cycle = [c for c in sccs if len(c) > 1]
    assert len(cycle) == 1
    assert set(cycle[0]) == {"A", "B"}

    batches = topo_batches(nodes, edges)
    ab_batch = next(b for b in batches if set(b) & {"A", "B"})
    assert set(ab_batch) == {"A", "B"}
    assert _index_of(batches, "C") < _index_of(batches, "A")


def test_self_loop_does_not_merge_with_others() -> None:
    nodes = {"A", "B"}
    edges = [("A", "A"), ("A", "B")]
    sccs = strongly_connected_components(nodes, edges)
    assert {"A"} in [set(c) for c in sccs]
    assert {"B"} in [set(c) for c in sccs]


def test_disconnected_nodes_all_present() -> None:
    nodes = {"A", "B", "C"}
    edges: list[tuple[str, str]] = []
    batches = topo_batches(nodes, edges)
    flattened = {n for batch in batches for n in batch}
    assert flattened == nodes


def test_larger_cycle_of_three() -> None:
    nodes = {"A", "B", "C", "D"}
    edges = [("A", "B"), ("B", "C"), ("C", "A"), ("A", "D")]
    batches = topo_batches(nodes, edges)
    cycle_batch = next(b for b in batches if len(b) == 3)
    assert set(cycle_batch) == {"A", "B", "C"}
    assert _index_of(batches, "D") < _index_of(batches, "A")
