#!/usr/bin/env python3
import os
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# Create visualizations folder
OUTPUT_DIR = "/home/shreyas-k/.gemini/antigravity/scratch/5g-mcp-automation/visualizations"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Custom color palette for premium dark-mode look
BG_COLOR = "#0E1117"      # Dark slate background
PANEL_COLOR = "#1A1D24"   # Node/panel gray
TEXT_COLOR = "#E2E8F0"    # Crisp light gray
BORDER_COLOR = "#3A3F4C"  # Muted silver
CYAN = "#06B6D4"          # Control plane links / CP Nodes
MAGENTA = "#EC4899"       # User plane links / UP Nodes
YELLOW = "#F59E0B"        # Databases / Mongo
GREEN = "#10B981"         # UE / active flows
MUTED = "#64748B"         # Grid / inactive

# Apply global Matplotlib parameters for consistency
plt.rcParams.update({
    "figure.facecolor": BG_COLOR,
    "axes.facecolor": BG_COLOR,
    "text.color": TEXT_COLOR,
    "axes.labelcolor": TEXT_COLOR,
    "xtick.color": TEXT_COLOR,
    "ytick.color": TEXT_COLOR,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "savefig.facecolor": BG_COLOR,
    "savefig.edgecolor": BG_COLOR
})

def draw_network_topology():
    """Generates the 5G Core Service Based Network Topology Diagram."""
    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
    G = nx.Graph()

    # Define Node categories and colors
    ue_nodes = ["UE"]
    ran_nodes = ["gNodeB"]
    cp_nodes = ["AMF", "SMF", "NRF", "SCP", "UDM", "UDR", "AUSF", "NSSF", "BSF"]
    up_nodes = ["UPF"]
    db_nodes = ["MongoDB"]

    # Assign positions in a logical 5G layout
    pos = {
        "UE": (-4, 0),
        "gNodeB": (-2, 0),
        "UPF": (0, -2),
        "AMF": (0, 1),
        "SMF": (2, -1),
        "SCP": (2, 2.5),
        "NRF": (4, 2.5),
        "NSSF": (-2, 2.5),
        "BSF": (0, 2.5),
        "AUSF": (4, 1),
        "UDM": (4, -0.5),
        "UDR": (6, -0.5),
        "MongoDB": (6, -2),
    }

    # Add nodes to graph
    for node in pos:
        G.add_node(node)

    # Add interfaces (edges)
    edges_cp = [
        ("UE", "gNodeB", "N1 (NAS)"),
        ("gNodeB", "AMF", "N2 (NGAP)"),
        ("AMF", "SMF", "N11"),
        ("AMF", "SCP", "Namf"),
        ("SMF", "SCP", "Nsmf"),
        ("AUSF", "SCP", "Nausf"),
        ("UDM", "SCP", "Nudm"),
        ("UDR", "SCP", "Nudr"),
        ("NSSF", "SCP", "Nnssf"),
        ("BSF", "SCP", "Nbsf"),
        ("NRF", "SCP", "Nnrf"),
        ("UDM", "UDR", "Nidr"),
        ("AUSF", "UDM", "N13"),
    ]
    edges_up = [
        ("gNodeB", "UPF", "N3 (GTP-U)"),
        ("SMF", "UPF", "N4 (PFCP)"),
    ]
    edges_db = [
        ("UDR", "MongoDB", "BSON/TCP"),
    ]

    # Combine edges for drawing
    for u, v, label in edges_cp + edges_up + edges_db:
        G.add_edge(u, v, label=label)

    # Draw Control Plane Edges (Cyan)
    nx.draw_networkx_edges(G, pos, edgelist=[(u,v) for u,v,l in edges_cp], edge_color=CYAN, width=2, style="dashed", ax=ax)
    # Draw User Plane Edges (Magenta)
    nx.draw_networkx_edges(G, pos, edgelist=[(u,v) for u,v,l in edges_up], edge_color=MAGENTA, width=3, ax=ax)
    # Draw Database Edges (Yellow)
    nx.draw_networkx_edges(G, pos, edgelist=[(u,v) for u,v,l in edges_db], edge_color=YELLOW, width=2, ax=ax)

    # Draw Nodes with distinct colors and shapes
    nx.draw_networkx_nodes(G, pos, nodelist=ue_nodes, node_color=GREEN, node_shape="o", node_size=1200, edgecolors=TEXT_COLOR, linewidths=1.5, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=ran_nodes, node_color=GREEN, node_shape="^", node_size=1200, edgecolors=TEXT_COLOR, linewidths=1.5, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=cp_nodes, node_color=CYAN, node_shape="s", node_size=1400, edgecolors=TEXT_COLOR, linewidths=1.5, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=up_nodes, node_color=MAGENTA, node_shape="D", node_size=1400, edgecolors=TEXT_COLOR, linewidths=1.5, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=db_nodes, node_color=YELLOW, node_shape="p", node_size=1400, edgecolors=TEXT_COLOR, linewidths=1.5, ax=ax)

    # Draw Node Labels
    nx.draw_networkx_labels(G, pos, font_size=10, font_color=TEXT_COLOR, font_weight="bold", ax=ax)

    # Draw Edge Interface Labels
    edge_labels = {(u, v): l for u, v, l in edges_cp + edges_up + edges_db}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8, font_color=MUTED, bbox=dict(facecolor=BG_COLOR, edgecolor="none", alpha=0.8), ax=ax)

    # Custom Legend
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker='o', color='none', label='User Equipment (UE)', markerfacecolor=GREEN, markersize=10),
            plt.Line2D([0], [0], marker='^', color='none', label='gNodeB (Simulated RAN)', markerfacecolor=GREEN, markersize=10),
            plt.Line2D([0], [0], marker='s', color='none', label='Control Plane NFs (SBI)', markerfacecolor=CYAN, markersize=10),
            plt.Line2D([0], [0], marker='D', color='none', label='User Plane Function (UPF)', markerfacecolor=MAGENTA, markersize=10),
            plt.Line2D([0], [0], marker='p', color='none', label='MongoDB Subscriber DB', markerfacecolor=YELLOW, markersize=10),
        ],
        loc="upper left",
        facecolor=PANEL_COLOR,
        edgecolor=BORDER_COLOR
    )

    ax.set_title("Open5GS 5G Standalone (SA) Core - Lab Topology & Interface Map", fontsize=16, fontweight="bold", pad=20)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/5g_network_topology.png", facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()

def draw_call_flow():
    """Generates a premium sequence/call-flow diagram for 5G Registration & Session Setup."""
    fig, ax = plt.subplots(figsize=(12, 9), dpi=150)
    ax.set_xlim(-0.5, 6.5)
    ax.set_ylim(-1, 12)

    # Define lifeline columns
    nodes = ["UE", "gNB", "AMF", "AUSF", "UDM", "SMF", "UPF"]
    x_pos = {nodes[i]: i for i in range(len(nodes))}

    # Draw lifeline pillars
    for node, x in x_pos.items():
        ax.plot([x, x], [-0.5, 11], color=MUTED, linestyle=":", alpha=0.5)
        # Bounding box for node headers
        ax.text(x, 11.3, node, ha="center", va="center", fontsize=12, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.5", facecolor=PANEL_COLOR, edgecolor=BORDER_COLOR, alpha=1.0))

    # Define message exchanges (y-level, source, dest, label, color)
    messages = [
        (10.2, "UE", "gNB", "RRC Connection Request", GREEN),
        (9.6, "gNB", "UE", "RRC Connection Setup Complete", GREEN),
        (8.8, "UE", "gNB", "NAS Registration Request (SUCI)", CYAN),
        (8.2, "gNB", "AMF", "NGAP Initial UE Message (NAS Reg Req)", CYAN),
        (7.4, "AMF", "AUSF", "Nausf_UEAuthentication Request", CYAN),
        (6.8, "AUSF", "UDM", "Nudm_UEAuthentication Request", CYAN),
        (6.2, "UDM", "AUSF", "Authentication Vectors (RAND, AUTN)", CYAN),
        (5.6, "AMF", "UE", "Downlink NAS Transport (Auth Challenge)", CYAN),
        (4.8, "UE", "AMF", "Uplink NAS Transport (Auth Response RES*)", CYAN),
        (4.0, "AMF", "UE", "NAS Security Mode Command", CYAN),
        (3.4, "UE", "AMF", "NAS Security Mode Complete", CYAN),
        (2.6, "AMF", "UE", "NAS Registration Accept (GUTI assigned)", CYAN),
        (1.8, "UE", "AMF", "NAS PDU Session Establishment Request (APN=internet)", MAGENTA),
        (1.2, "AMF", "SMF", "Nsmf_PDUSession_CreateSMContext Request", MAGENTA),
        (0.6, "SMF", "UPF", "N4 PFCP Session Establishment Request", MAGENTA),
        (0.0, "UPF", "UE", "PDU Session Accept & GTP-U Tunnel UP (IP assigned)", GREEN)
    ]

    # Draw arrows and message descriptions
    for y, src, dst, label, color in messages:
        x_src = x_pos[src]
        x_dst = x_pos[dst]
        
        # Determine arrow direction
        dx = x_dst - x_src
        ax.annotate("", xy=(x_dst, y), xytext=(x_src, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.8, shrinkA=0, shrinkB=0))
        
        # Label offset to prevent overlapping lifelines
        text_x = x_src + dx / 2.0
        ax.text(text_x, y + 0.15, label, ha="center", va="bottom", fontsize=8.5, color=TEXT_COLOR,
                bbox=dict(facecolor=BG_COLOR, edgecolor="none", alpha=0.9, boxstyle="round,pad=0.2"))

    ax.axis("off")
    ax.set_title("5G Standalone (SA) UE Registration & PDU Session Call Flow", fontsize=16, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/5g_call_flow.png", facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()

def draw_architecture_overview():
    """Generates the 5G Service Based Architecture (SBA) Control Plane vs User Plane split block diagram."""
    fig, ax = plt.subplots(figsize=(11, 7), dpi=150)
    ax.set_xlim(-1, 11)
    ax.set_ylim(-1, 8)

    # 1. SBI Bus (Service Based Interface)
    ax.fill_between([-0.5, 9.5], 5.8, 6.2, color=CYAN, alpha=0.3, label="Control Plane SBI Bus")
    ax.plot([-0.5, 9.5], [6.0, 6.0], color=CYAN, lw=4, label="Service Based Interface (SBI)")
    ax.text(4.5, 6.4, "Service Based Architecture (SBA) - Control Plane Bus", ha="center", va="center", color=CYAN, fontweight="bold")

    # 2. Control Plane NFs
    cp_nfs = [
        ("NRF", 0), ("SCP", 2), ("AMF", 4), ("SMF", 6), ("UDM/UDR", 8), ("PCF", 1.0, 4.0), ("NSSF", 9.0, 4.0)
    ]
    for nf in cp_nfs:
        name = nf[0]
        x = nf[1]
        y = nf[2] if len(nf) > 2 else 4.8
        
        # Draw Box
        ax.text(x, y, name, ha="center", va="center", fontsize=11, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.6", facecolor=PANEL_COLOR, edgecolor=CYAN, lw=1.5))
        # Draw connection line to SBI Bus
        ax.plot([x, x], [y + 0.4 if y < 5 else y - 0.4, 6.0], color=CYAN, linestyle="-", lw=1.5)

    # 3. Access & User Plane (Bottom layer)
    ax.text(0, 1.5, "UE", ha="center", va="center", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.6", facecolor=PANEL_COLOR, edgecolor=GREEN, lw=1.5))
    ax.text(3, 1.5, "gNodeB\n(Simulated)", ha="center", va="center", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.6", facecolor=PANEL_COLOR, edgecolor=GREEN, lw=1.5))
    ax.text(6, 1.5, "UPF\n(User Plane)", ha="center", va="center", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.6", facecolor=PANEL_COLOR, edgecolor=MAGENTA, lw=1.5))
    ax.text(9, 1.5, "Data Network\n(Internet)", ha="center", va="center", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.6", facecolor=PANEL_COLOR, edgecolor=YELLOW, lw=1.5))

    # User Plane connections
    ax.annotate("N1 (NAS)", xy=(3, 4.2), xytext=(0, 2.1), arrowprops=dict(arrowstyle="<->", color=CYAN, linestyle="--", lw=1.5))
    ax.annotate("N2 (NGAP)", xy=(4, 4.2), xytext=(3, 2.1), arrowprops=dict(arrowstyle="<->", color=CYAN, lw=1.5))
    ax.annotate("N11 (NAS/PDU)", xy=(6, 4.2), xytext=(6, 2.1), arrowprops=dict(arrowstyle="<->", color=MUTED, linestyle=":", lw=1.5)) # AMF to SMF / SMF to UPF
    
    # N3 GTP Arrow
    ax.annotate("N3 GTP-U\nUser Plane", xy=(6, 1.5), xytext=(3.8, 1.5), arrowprops=dict(arrowstyle="->", color=MAGENTA, lw=3))
    # N6 internet Arrow
    ax.annotate("N6 (SGi)\nIP Traffic", xy=(9, 1.5), xytext=(6.8, 1.5), arrowprops=dict(arrowstyle="->", color=MAGENTA, lw=3))
    # N4 Control Plane association (SMF to UPF)
    ax.annotate("N4 PFCP Control", xy=(6, 2.1), xytext=(6, 4.2), arrowprops=dict(arrowstyle="<->", color=MAGENTA, linestyle="--", lw=2))

    ax.axis("off")
    ax.set_title("5G SA Service Based Architecture (SBA) Control Plane vs User Plane Split", fontsize=15, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/architecture_overview.png", facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()

def draw_traffic_heatmap():
    """Generates the Subscriber Slices and Live Data Traffic Heatmap."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    
    # Create mock metrics for 4 network slices over a 12-hour period
    slices = ["Slice 1: Enhanced Mobile Broadband (eMBB)", 
              "Slice 2: Ultra-Reliable Low Latency (URLLC)", 
              "Slice 3: Massive IoT (mMTC)", 
              "Slice 4: IMS/VoNR (Voice)"]
    hours = [f"{h}:00" for h in range(8, 20)]
    
    # Generate structured mock traffic metrics (in Mbps)
    traffic_matrix = np.array([
        [420, 480, 520, 610, 580, 640, 720, 890, 940, 810, 690, 510],  # eMBB (High bandwidth peak at evening)
        [15,  18,  22,  25,  28,  30,  34,  45,  48,  42,  38,  32],   # URLLC (Stable low latency)
        [85,  92,  98,  105, 110, 115, 120, 140, 145, 130, 110, 95],   # mMTC (Moderate background IoT)
        [120, 135, 110, 95,  85,  140, 165, 210, 240, 180, 150, 110]   # IMS (Peaks at lunch & afterwork)
    ])

    im = ax.imshow(traffic_matrix, cmap="YlGnBu", aspect="auto")
    
    # Grid ticks and labels
    ax.set_xticks(np.arange(len(hours)))
    ax.set_yticks(np.arange(len(slices)))
    ax.set_xticklabels(hours, fontsize=9)
    ax.set_yticklabels(slices, fontsize=10, fontweight="bold")
    
    # Rotate tick labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    # Add text inside cells
    for i in range(len(slices)):
        for j in range(len(hours)):
            val = traffic_matrix[i, j]
            # Use light text for dark blocks, dark text for light blocks
            color = "white" if val > 400 else BG_COLOR
            ax.text(j, i, f"{val}M", ha="center", va="center", color=color, fontsize=8.5, fontweight="bold")

    # Add Colorbar with customized colors
    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.set_ylabel("Data Throughput (Mbps)", rotation=-90, va="bottom")

    ax.set_title("5G Lab Network Slice Traffic Throughput Heatmap (24h Activity Loop)", fontsize=14, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/traffic_heatmap.png", facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    print("Generating 5G Automation Lab premium dark-mode visualizations...")
    draw_network_topology()
    print("✓ Successfully generated Network Topology Diagram (5g_network_topology.png)")
    draw_call_flow()
    print("✓ Successfully generated Call Flow Sequence Diagram (5g_call_flow.png)")
    draw_architecture_overview()
    print("✓ Successfully generated Architecture Overview Block Diagram (architecture_overview.png)")
    draw_traffic_heatmap()
    print("✓ Successfully generated Traffic Heatmap (traffic_heatmap.png)")
    print("=== All visualizations generated inside /visualizations/ directory! ===")
