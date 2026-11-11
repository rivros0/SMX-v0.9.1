"""
Visualizzazione a rete delle somiglianze tra elaborati SMX.

La matrice e i confronti sono calcolati una sola volta in similarity.py.
Questo modulo si occupa esclusivamente della rappresentazione e dei filtri.
Non accede ai file degli studenti e non modifica alcun elaborato.
"""

import math
import tkinter as tk
from tkinter import filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


def _connected_components(number_of_nodes, edges):
    """Individua i gruppi connessi includendo anche eventuali nodi isolati."""
    adjacency = {}
    for index in range(number_of_nodes):
        adjacency[index] = set()

    for first, second, _value in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)

    visited = set()
    components = []
    for node in range(number_of_nodes):
        if node in visited:
            continue

        stack = [node]
        group = []
        visited.add(node)
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbour in sorted(adjacency[current]):
                if neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)

        components.append(sorted(group))

    components.sort(key=lambda group: (-len(group), group[0]))
    return components


def _layout_components(components):
    """
    Posiziona ogni componente in un proprio settore della figura.
    Il layout è deterministico e non richiede librerie aggiuntive.
    """
    positions = {}
    number_of_groups = len(components)
    if number_of_groups == 0:
        return positions

    columns = max(1, int(math.ceil(math.sqrt(number_of_groups))))
    for index, group in enumerate(components):
        column = index % columns
        row = index // columns
        center_x = column * 4.7
        center_y = -row * 4.7

        if len(group) == 1:
            positions[group[0]] = (center_x, center_y)
            continue

        radius = max(1.1, 0.52 * len(group))
        for position_in_group, node in enumerate(group):
            angle = 2.0 * math.pi * position_in_group / len(group)
            angle = angle + math.pi / 2.0
            positions[node] = (
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle),
            )

    return positions


def _point_to_segment_distance(point_x, point_y, start_x, start_y, end_x, end_y):
    """Distanza in pixel dal cursore a un arco, per selezione con il mouse."""
    dx = end_x - start_x
    dy = end_y - start_y
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(point_x - start_x, point_y - start_y)

    projection = (
        (point_x - start_x) * dx + (point_y - start_y) * dy
    ) / length_squared
    projection = max(0.0, min(1.0, projection))
    closest_x = start_x + projection * dx
    closest_y = start_y + projection * dy
    return math.hypot(point_x - closest_x, point_y - closest_y)


def create_similarity_graph(parent, files, matrix, labels, open_pair):
    """
    Crea il grafo Tkinter/Matplotlib nel frame parent.

    open_pair(first_index, second_index) apre il confronto originale.
    matrix è la stessa matrice percentuale utilizzata dalla heatmap.
    """
    controls = tk.Frame(parent, bg="white")
    controls.pack(side="top", fill="x", padx=8, pady=6)

    tk.Label(
        controls, text="Similarità minima (%):", bg="white"
    ).pack(side="left", padx=(0, 4))

    threshold = tk.IntVar(value=70)
    slider = tk.Scale(
        controls, from_=0, to=100, orient="horizontal",
        resolution=1, variable=threshold, length=180,
        bg="white", highlightthickness=0,
    )
    slider.pack(side="left")

    show_isolated = tk.BooleanVar(value=True)
    show_percentages = tk.BooleanVar(value=True)

    tk.Checkbutton(
        controls, text="Mostra isolati", variable=show_isolated, bg="white"
    ).pack(side="left", padx=8)
    tk.Checkbutton(
        controls, text="Mostra percentuali", variable=show_percentages, bg="white"
    ).pack(side="left", padx=8)

    info_label = tk.Label(controls, text="", bg="white", anchor="w")
    info_label.pack(side="left", padx=12)

    figure = Figure(figsize=(10, 7), dpi=100)
    axes = figure.add_subplot(111)
    canvas = FigureCanvasTkAgg(figure, master=parent)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    toolbar_frame = tk.Frame(parent)
    toolbar_frame.pack(side="bottom", fill="x")
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    toolbar.update()

    # Memorizza soltanto gli archi attualmente visibili e selezionabili.
    visible_edges = []
    current_positions = {}

    def redraw():
        nonlocal visible_edges, current_positions
        axes.clear()
        visible_edges = []

        cutoff = float(threshold.get())
        edges = []
        connected_nodes = set()
        for first in range(len(files)):
            for second in range(first + 1, len(files)):
                value = float(matrix[first, second])
                if value >= cutoff:
                    edges.append((first, second, value))
                    connected_nodes.add(first)
                    connected_nodes.add(second)

        components = _connected_components(len(files), edges)
        if not show_isolated.get():
            components = [
                group for group in components
                if len(group) > 1
            ]
        current_positions = _layout_components(components)

        # Gli archi sono disegnati per primi, dietro ai nodi.
        for first, second, value in edges:
            if first not in current_positions or second not in current_positions:
                continue
            start = current_positions[first]
            end = current_positions[second]
            strength = max(0.0, min(1.0, value / 100.0))
            thickness = 1.0 + 5.0 * strength
            line_color = "#bf3f44"
            if value < 80.0:
                line_color = "#c78b35"

            axes.plot(
                [start[0], end[0]], [start[1], end[1]],
                color=line_color, linewidth=thickness,
                alpha=0.72, zorder=1,
            )
            visible_edges.append((first, second, value))

            if show_percentages.get():
                midpoint_x = (start[0] + end[0]) / 2.0
                midpoint_y = (start[1] + end[1]) / 2.0
                axes.text(
                    midpoint_x, midpoint_y, "{:.0f}%".format(value),
                    fontsize=8, color="#263238", ha="center", va="center",
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8},
                    zorder=3,
                )

        for node, position in current_positions.items():
            axes.scatter(
                [position[0]], [position[1]], s=950,
                facecolor="#e3f2fd", edgecolor="#245789",
                linewidth=1.5, zorder=4,
            )
            axes.text(
                position[0], position[1], labels[node],
                ha="center", va="center", fontsize=8,
                color="#173957", zorder=5,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.65},
            )

        axes.set_aspect("equal", adjustable="datalim")
        axes.axis("off")
        axes.margins(0.20)
        axes.set_title("Rete delle somiglianze tra elaborati", fontsize=13)

        group_count = sum(1 for group in components if len(group) > 1)
        info_label.configure(
            text="{} collegamenti | {} gruppi".format(len(visible_edges), group_count)
        )
        canvas.draw_idle()

    def on_graph_click(event):
        """Il click su un arco apre lo stesso dettaglio della matrice."""
        if event.inaxes != axes:
            return
        if event.x is None or event.y is None:
            return
        if toolbar.mode:
            return

        selected_pair = None
        minimum_distance = 12.0
        for first, second, _value in visible_edges:
            start = axes.transData.transform(current_positions[first])
            end = axes.transData.transform(current_positions[second])
            distance = _point_to_segment_distance(
                event.x, event.y, start[0], start[1], end[0], end[1]
            )
            if distance < minimum_distance:
                minimum_distance = distance
                selected_pair = (first, second)

        if selected_pair is not None:
            open_pair(selected_pair[0], selected_pair[1])

    def save_image():
        destination = filedialog.asksaveasfilename(
            parent=parent,
            title="Esporta grafo similarità",
            defaultextension=".png",
            filetypes=[("Immagine PNG", "*.png")],
        )
        if not destination:
            return
        try:
            figure.savefig(destination, dpi=180, bbox_inches="tight")
        except OSError as error:
            messagebox.showerror("Esportazione grafo", str(error), parent=parent)

    def reset_view():
        redraw()

    export_button = tk.Button(
        controls, text="Esporta PNG", command=save_image
    )
    export_button.pack(side="right", padx=4)
    reset_button = tk.Button(
        controls, text="Adatta vista", command=reset_view
    )
    reset_button.pack(side="right", padx=4)

    def on_threshold_change(_value):
        redraw()

    slider.configure(command=on_threshold_change)
    def _on_filter_change(*_args):
        redraw()

    show_isolated.trace_add("write", _on_filter_change)
    show_percentages.trace_add("write", _on_filter_change)
    canvas.mpl_connect("button_press_event", on_graph_click)
    redraw()
    return figure
