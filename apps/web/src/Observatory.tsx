import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowUpRight,
  AudioLines,
  CircleHelp,
  Compass,
  Database,
  GitBranch,
  Layers3,
  Maximize2,
  Minus,
  Network,
  Pause,
  Play,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from 'lucide-react';
import { api } from './api';
import './observatory.css';

type Screen = 'network' | 'learning' | 'universe' | 'simulation';
type ModelSummary = {
  model_id: string;
  family: string;
  state: string;
  dataset_id: string;
  label_target?: string;
  created_at?: number;
  artifact_sha256?: string;
  has_learning_history: boolean;
  validation?: { brier?: number; rows?: number; base_episodes?: number } | null;
  test?: { brier?: number; rows?: number; base_episodes?: number } | null;
  timesteps?: number;
  training_episodes?: number;
  configuration: Record<string, unknown>;
};
type GraphNode = {
  id: string;
  identity: string;
  kind: string;
  title: string;
  summary: string;
  state: string;
  created_at?: number;
  family?: string;
  dataset_id?: string;
  label_target?: string;
  has_learning_history?: boolean;
  evaluation_design?: string;
  base_episodes?: number;
  progress?: { done?: number; total?: number; unit?: string };
};
type GraphEdge = { source: string; target: string; relationship: string };
type TournamentSummary = {
  tournament_id: string;
  created_at?: number;
  evaluation_design?: string;
  base_episodes?: number;
  variants?: number;
  conclusion?: string;
  dataset_id?: string;
  feature_schema?: string[];
};
type ObservatoryData = {
  generated_at: number;
  read_only: boolean;
  bounded: { artifact_counts_by_type: Record<string, number>; truncated: boolean };
  models: ModelSummary[];
  network_models: ModelSummary[];
  training_runs: {
    model_id?: string;
    job_id?: string;
    family: string;
    state: string;
    created_at?: number;
    has_learning_history: boolean;
    progress?: { done?: number; total?: number; unit?: string };
  }[];
  active_training_records: number;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  simulations: TournamentSummary[];
  interpretation: string;
};
type NetworkData = {
  model: {
    model_id: string;
    state: string;
    dataset_id: string;
    label_target: string;
    created_at?: number;
    architecture: number[];
    artifact_sha256: string;
  };
  dataset: {
    id: string;
    provenance: string;
    partition: string;
    label_target?: string;
    validation_count: number;
    limitations: string[];
  };
  sample: {
    index: number;
    family: string;
    execution_model: string;
    decision_scope?: string;
    base_episode_id?: string;
  };
  input: {
    features: { name: string; raw_value: number; model_value: number; excluded: boolean }[];
  };
  activations: number[][];
  connections: { from_layer: number; to_layer: number; weights: number[][]; bias: number[] }[];
  prediction: { probability: number; logit: number; meaning: string };
};
type ModelDetail = ModelSummary & {
  curves?: {
    epoch?: number;
    timesteps?: number;
    training_loss?: number;
    validation_loss?: number;
    episode_return?: number;
    episode_length?: number;
    net_simulated_pnl?: number;
    action_counts?: Record<string, number>;
  }[];
  limitations?: string[];
  best_epoch?: number;
  architecture?: { policy?: number[]; value?: number[]; algorithm?: string };
};
type TournamentDetail = {
  tournament_id: string;
  evaluation_design?: string;
  base_episodes?: number;
  variants?: number;
  leaderboard?: { policy: string; mean_pnl: number; cvar_05_loss: number; score: number }[];
  conclusion?: string;
  economically_verified?: boolean;
  uncertainty_note?: string;
  configuration?: { dataset_id?: string };
};
type TournamentRow = {
  id: string;
  policy: string;
  family: string;
  execution_model: string;
  passed: boolean;
  metrics: { net_simulated_pnl: string; partial_orders: number; decisions?: number };
};
type ReplayData = {
  row: TournamentRow;
  decisions: {
    action?: number | string;
    requested_action?: string;
    explanation?: { policy?: string; reason?: string; mathematically_eligible?: boolean };
    observation?: number[];
  }[];
  result: {
    journal: {
      kind: string;
      time_ms: number;
      index: number;
      before: Record<string, unknown>;
      after: Record<string, unknown>;
      command: unknown;
    }[];
    metrics: Record<string, unknown>;
    scenario: { provenance?: string; market?: { question?: string; source?: string } };
    classification?: string;
    passed: boolean;
    economically_verified?: boolean;
  };
};

const screenTabs: { id: Screen; label: string; detail: string; icon: typeof Network }[] = [
  { id: 'network', label: 'Neural network', detail: 'Explore a real model', icon: Network },
  { id: 'learning', label: 'How it learns', detail: 'Replay saved training', icon: Activity },
  { id: 'universe', label: 'Research universe', detail: 'Follow evidence links', icon: Waypoints },
  {
    id: 'simulation',
    label: 'Simulations',
    detail: 'Inspect a recorded decision',
    icon: AudioLines,
  },
];
const stageNames = ['Inputs', 'Pattern layer', 'Combination layer', 'Prediction'];
const networkLayerX = [230, 465, 700, 930];
const formatTime = (seconds?: number) =>
  seconds
    ? new Date(seconds * 1000).toLocaleString(undefined, { dateStyle: 'medium' })
    : 'Saved record';
const number = (value: number | undefined, digits = 3) =>
  value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits);
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const decisionFeatureLabels: Record<string, string> = {
  ask_sum: 'Combined ask prices',
  bid_sum: 'Combined bid prices',
  min_ask_depth: 'Shallowest ask depth',
  max_ask_depth: 'Deepest ask depth',
  min_top_depth: 'Shallowest top depth',
  max_spread: 'Widest bid/ask spread',
  max_age_ms: 'Age of the oldest quote',
  fee_rate: 'Trading fee rate',
  capital_available: 'Available virtual capital',
  locked_capital: 'Reserved virtual capital',
  unmatched_quantity: 'Unmatched share quantity',
  proposed_quantity: 'Proposed share quantity',
  conditional_edge: 'Estimated proposal edge',
  latency_ms: 'Execution delay',
  jitter_ms: 'Execution-delay variation',
  liquidity_fraction: 'Available liquidity',
  adverse_ticks: 'Adverse price movement',
  ack_delay_ms: 'Order acknowledgement delay',
  observation_latency_ms: 'Observation delay',
};
const labelTarget = (target?: string) =>
  ({
    completion: 'complete together',
    unmatched: 'leave shares unmatched',
    persistence: 'remain available at arrival',
  })[target ?? ''] ??
  target?.replaceAll('_', ' ') ??
  'the saved research target';

function nodeColor(kind: string) {
  return (
    {
      dataset: '#a4a998',
      model: '#80b7c2',
      experiment: '#d4b16e',
      finding: '#c68d87',
      plan: '#b2a2c7',
      director: '#d39c6e',
      observation: '#8eabc4',
      training: '#73c7a2',
    }[kind] ?? '#8c99aa'
  );
}

function graphLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  const width = 1080;
  const height = 680;
  const centers: Record<string, [number, number, number]> = {
    dataset: [135, 165, 74],
    observation: [125, 440, 58],
    model: [365, 185, 145],
    experiment: [650, 185, 142],
    finding: [935, 235, 155],
    director: [365, 520, 93],
    plan: [670, 510, 102],
    training: [145, 600, 52],
  };
  const positions = new Map<string, { x: number; y: number; ax: number; ay: number }>();
  const categories = new Map<string, GraphNode[]>();
  for (const node of nodes) categories.set(node.kind, [...(categories.get(node.kind) ?? []), node]);
  for (const [kind, group] of categories) {
    const [cx, cy, radius] = centers[kind] ?? [540, 340, 100];
    group.forEach((node, index) => {
      const angle = index * 2.399963 + kind.length * 0.17;
      const distance =
        radius * (0.18 + 0.82 * Math.sqrt((index + 0.6) / Math.max(group.length, 1)));
      positions.set(node.id, {
        x: cx + Math.cos(angle) * distance,
        y: cy + Math.sin(angle) * distance,
        ax: cx + Math.cos(angle) * distance * 0.68,
        ay: cy + Math.sin(angle) * distance * 0.68,
      });
    });
  }
  const validEdges = edges.filter(
    (edge) => positions.has(edge.source) && positions.has(edge.target),
  );
  for (let iteration = 0; iteration < 52; iteration += 1) {
    const cooling = 0.14 * (1 - iteration / 65);
    for (let left = 0; left < nodes.length; left += 1) {
      const a = positions.get(nodes[left].id);
      if (!a) continue;
      let fx = (a.ax - a.x) * 0.012;
      let fy = (a.ay - a.y) * 0.012;
      for (let right = left + 1; right < nodes.length; right += 1) {
        const b = positions.get(nodes[right].id);
        if (!b) continue;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const distance2 = dx * dx + dy * dy;
        if (distance2 > 36000) continue;
        if (distance2 < 4) {
          dx += left % 2 ? 1.7 : -1.7;
          dy += right % 2 ? 1.3 : -1.3;
        }
        const distance = Math.sqrt(dx * dx + dy * dy);
        const push = Math.min(5, 1120 / Math.max(distance2, 32));
        fx += (dx / distance) * push;
        fy += (dy / distance) * push;
        const pull = ((b.x - a.x) * 1120) / Math.max(distance2, 32) / distance;
        fx -= dx * pull * 0.00032;
        fy -= dy * pull * 0.00032;
      }
      positions.set(nodes[left].id, {
        ...a,
        x: Math.max(38, Math.min(width - 38, a.x + fx * cooling)),
        y: Math.max(38, Math.min(height - 38, a.y + fy * cooling)),
      });
    }
    for (const edge of validEdges) {
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      // Keep explicit links legible while preserving the artifact type clusters.
      const pull = (distance - 82) * 0.00045 * cooling;
      positions.set(edge.source, { ...a, x: a.x + dx * pull, y: a.y + dy * pull });
      positions.set(edge.target, { ...b, x: b.x - dx * pull, y: b.y - dy * pull });
    }
  }
  return positions;
}

function NetworkCanvas({
  data,
  selected,
  onSelect,
  activeLayer,
  animationStage,
  animationProgress,
}: {
  data: NetworkData;
  selected:
    | { type: 'neuron'; layer: number; index: number }
    | { type: 'connection'; layer: number; from: number; to: number; weight: number };
  onSelect: (selection: typeof selected) => void;
  activeLayer: number;
  animationStage: number | null;
  animationProgress: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean; panX: number; panY: number } | null>(
    null,
  );
  const [view, setView] = useState({ zoom: 1, panX: 0, panY: 0 });
  const [size, setSize] = useState({ width: 960, height: 620 });
  const [hovered, setHovered] = useState<string | null>(null);
  const width = 1050;
  const height = 620;
  const nodes = useMemo(
    () =>
      data.activations.map((values, layer) =>
        values.map((value, index) => ({ layer, index, value })),
      ),
    [data.activations],
  );
  const coordinates = useMemo(
    () =>
      nodes.map((layer, layerIndex) =>
        layer.map((neuron, index) => ({
          ...neuron,
          x: networkLayerX[layerIndex],
          y:
            height / 2 +
            (index - (layer.length - 1) / 2) * Math.min(17, 470 / Math.max(layer.length - 1, 1)),
        })),
      ),
    [nodes],
  );

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() =>
      setSize({ width: canvas.clientWidth || 960, height: canvas.clientHeight || 620 }),
    );
    observer.observe(canvas);
    setSize({ width: canvas.clientWidth || 960, height: canvas.clientHeight || 620 });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.width * ratio);
    canvas.height = Math.round(size.height * ratio);
    const context = canvas.getContext('2d');
    if (!context) return;
    const fit = Math.min(size.width / width, size.height / height);
    const originX = (size.width - width * fit * view.zoom) / 2 + view.panX;
    const originY = (size.height - height * fit * view.zoom) / 2 + view.panY;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, size.width, size.height);
    context.fillStyle = '#0c1117';
    context.fillRect(0, 0, size.width, size.height);
    context.save();
    context.translate(originX, originY);
    context.scale(fit * view.zoom, fit * view.zoom);

    context.strokeStyle = 'rgba(159, 178, 194, .055)';
    context.lineWidth = 1;
    for (let x = 22; x < width; x += 42) {
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
    }
    for (let y = 18; y < height; y += 42) {
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }
    const columnNames = ['OBSERVABLE INPUTS', 'PATTERN LAYER', 'COMBINATION LAYER', 'MODEL OUTPUT'];
    columnNames.forEach((name, index) => {
      context.fillStyle = index === activeLayer ? '#d5bb86' : '#727e8c';
      context.font = '600 10px Inter, sans-serif';
      context.textAlign = index === 0 ? 'left' : 'center';
      context.fillText(name, index === 0 ? 28 : networkLayerX[index], 35);
      if (index === 0) {
        context.fillStyle = '#5f6b78';
        context.font = '10px Inter, sans-serif';
        context.fillText('19 saved decision features', 28, 52);
      }
    });

    const selectedConnection = selected.type === 'connection' ? selected : null;
    for (const connection of data.connections) {
      const layer = connection.from_layer;
      const sourceNodes = coordinates[layer];
      const targetNodes = coordinates[layer + 1];
      if (!sourceNodes || !targetNodes) continue;
      const matrix = connection.weights;
      const maxWeight = Math.max(0.000001, ...matrix.flat().map((value) => Math.abs(value)));
      for (let to = 0; to < matrix.length; to += 1) {
        for (let from = 0; from < matrix[to].length; from += 1) {
          const weight = matrix[to][from];
          const strength = Math.abs(weight) / maxWeight;
          const a = sourceNodes[from];
          const b = targetNodes[to];
          if (!a || !b) continue;
          const chosen =
            selectedConnection?.layer === layer &&
            selectedConnection.from === from &&
            selectedConnection.to === to;
          const dimForLayer = activeLayer !== layer && selected.type === 'neuron';
          context.beginPath();
          context.moveTo(a.x, a.y);
          context.lineTo(b.x, b.y);
          context.strokeStyle = chosen
            ? '#f5e5be'
            : weight >= 0
              ? `rgba(107, 188, 165, ${Math.min(0.48, 0.045 + strength * 0.39) * (dimForLayer ? 0.42 : 1)})`
              : `rgba(208, 163, 103, ${Math.min(0.46, 0.035 + strength * 0.37) * (dimForLayer ? 0.42 : 1)})`;
          context.lineWidth = chosen ? 2.2 : 0.38 + strength * 1.15;
          context.stroke();
        }
      }
    }

    if (animationStage != null) {
      const connection = data.connections[animationStage];
      const sourceNodes = coordinates[animationStage];
      const targetNodes = coordinates[animationStage + 1];
      if (connection && sourceNodes && targetNodes) {
        const candidates: { from: number; to: number; strength: number }[] = [];
        connection.weights.forEach((weights, to) =>
          weights.forEach((weight, from) => {
            candidates.push({
              from,
              to,
              strength: Math.abs(weight * (data.activations[animationStage]?.[from] ?? 0)),
            });
          }),
        );
        candidates.sort((a, b) => b.strength - a.strength);
        const maxSignal = candidates[0]?.strength || 1;
        for (const signal of candidates.slice(0, 72)) {
          const from = sourceNodes[signal.from];
          const to = targetNodes[signal.to];
          if (!from || !to) continue;
          const t = Math.max(0, Math.min(1, animationProgress));
          const x = from.x + (to.x - from.x) * t;
          const y = from.y + (to.y - from.y) * t;
          const alpha = 0.28 + 0.7 * (signal.strength / maxSignal);
          context.beginPath();
          context.arc(x, y, 1.4 + (1.3 * signal.strength) / maxSignal, 0, Math.PI * 2);
          context.fillStyle = `rgba(218, 236, 216, ${alpha})`;
          context.shadowBlur = 12;
          context.shadowColor = '#a7e8cc';
          context.fill();
          context.shadowBlur = 0;
        }
      }
    }

    coordinates.forEach((layer, layerIndex) => {
      for (const neuron of layer) {
        const selectedNeuron =
          selected.type === 'neuron' &&
          selected.layer === neuron.layer &&
          selected.index === neuron.index;
        const radius =
          layerIndex === 0
            ? 4.3
            : layerIndex === 3
              ? 12
              : Math.max(3.2, 5.1 - Math.max(0, layer.length - 32) * 0.035);
        const intensity = Math.tanh(Math.abs(neuron.value) / (layerIndex === 3 ? 0.5 : 2.3));
        const color =
          layerIndex === 0
            ? '#b4a58c'
            : layerIndex === 1
              ? '#80b7c2'
              : layerIndex === 2
                ? '#d3ad68'
                : '#a6d5b5';
        const active = `rgba(${layerIndex === 1 ? '128, 183, 194' : layerIndex === 2 ? '211, 173, 104' : '166, 213, 181'}, ${0.13 + intensity * 0.6})`;
        context.beginPath();
        context.arc(neuron.x, neuron.y, radius + (selectedNeuron ? 3 : 0), 0, Math.PI * 2);
        context.fillStyle = active;
        context.fill();
        context.strokeStyle = selectedNeuron ? '#f1ddae' : `${color}b8`;
        context.lineWidth = selectedNeuron ? 1.8 : 0.8;
        context.stroke();
        if (selectedNeuron || hovered === `${neuron.layer}:${neuron.index}`) {
          context.fillStyle = '#e4e7eb';
          context.font = '10px Inter, sans-serif';
          context.textAlign = layerIndex === 0 ? 'left' : layerIndex === 3 ? 'center' : 'left';
          const textX = layerIndex === 0 ? 15 : layerIndex === 3 ? neuron.x : neuron.x + 12;
          context.fillText(
            layerIndex === 0
              ? (data.input.features[neuron.index]?.name ?? '')
              : layerIndex === 3
                ? 'Prediction'
                : `Neuron ${neuron.index + 1}`,
            textX,
            neuron.y + 3,
          );
        }
      }
    });
    context.restore();
  }, [
    activeLayer,
    animationProgress,
    animationStage,
    coordinates,
    data,
    height,
    selected,
    size,
    view,
    width,
    hovered,
  ]);

  const worldPoint = (clientX: number, clientY: number) => {
    const fit = Math.min(size.width / width, size.height / height);
    return {
      x:
        (clientX -
          (ref.current?.getBoundingClientRect().left ?? 0) -
          (size.width - width * fit * view.zoom) / 2 -
          view.panX) /
        (fit * view.zoom),
      y:
        (clientY -
          (ref.current?.getBoundingClientRect().top ?? 0) -
          (size.height - height * fit * view.zoom) / 2 -
          view.panY) /
        (fit * view.zoom),
    };
  };
  const down = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    drag.current = {
      x: event.clientX,
      y: event.clientY,
      moved: false,
      panX: view.panX,
      panY: view.panY,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const move = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const active = drag.current;
    if (active) {
      const dx = event.clientX - active.x;
      const dy = event.clientY - active.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) active.moved = true;
      if (active.moved)
        setView((old) => ({ ...old, panX: active.panX + dx, panY: active.panY + dy }));
      return;
    }
    const point = worldPoint(event.clientX, event.clientY);
    let nearest: { id: string; distance: number } | null = null;
    for (let layerIndex = 0; layerIndex < coordinates.length; layerIndex += 1) {
      const layer = coordinates[layerIndex];
      for (const neuron of layer) {
        const distance = Math.hypot(point.x - neuron.x, point.y - neuron.y);
        if (distance < 12 && (!nearest || distance < nearest.distance))
          nearest = { id: `${layerIndex}:${neuron.index}`, distance };
      }
    }
    setHovered(nearest?.id ?? null);
  };
  const up = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const active = drag.current;
    drag.current = null;
    if (!active || active.moved) return;
    const point = worldPoint(event.clientX, event.clientY);
    let nearest: { layer: number; index: number; distance: number } | null = null;
    for (let layerIndex = 0; layerIndex < coordinates.length; layerIndex += 1) {
      const layer = coordinates[layerIndex];
      for (const neuron of layer) {
        const distance = Math.hypot(point.x - neuron.x, point.y - neuron.y);
        if (distance < 12 && (!nearest || distance < nearest.distance))
          nearest = { layer: layerIndex, index: neuron.index, distance };
      }
    }
    if (nearest) {
      onSelect({ type: 'neuron', layer: nearest.layer, index: nearest.index });
      return;
    }
    let candidate: {
      layer: number;
      from: number;
      to: number;
      weight: number;
      distance: number;
    } | null = null;
    for (const connection of data.connections) {
      const fromLayer = coordinates[connection.from_layer];
      const toLayer = coordinates[connection.to_layer];
      for (let to = 0; to < connection.weights.length; to += 1) {
        const weights = connection.weights[to];
        for (let from = 0; from < weights.length; from += 1) {
          const weight = weights[from];
          const a = fromLayer?.[from];
          const b = toLayer?.[to];
          if (!a || !b) continue;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const t = Math.max(
            0,
            Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / (dx * dx + dy * dy)),
          );
          const distance = Math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy));
          if (distance < 4 && (!candidate || distance < candidate.distance))
            candidate = { layer: connection.from_layer, from, to, weight, distance };
        }
      }
    }
    if (candidate)
      onSelect({
        type: 'connection',
        layer: candidate.layer,
        from: candidate.from,
        to: candidate.to,
        weight: candidate.weight,
      });
  };
  const zoom = (amount: number) =>
    setView((old) => ({ ...old, zoom: Math.max(0.55, Math.min(2.2, old.zoom * amount)) }));
  const wheel = (event: ReactWheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    zoom(event.deltaY < 0 ? 1.08 : 0.92);
  };

  return (
    <div className="obs-network-canvas-wrap">
      <canvas
        ref={ref}
        className="obs-network-canvas"
        aria-label="Interactive neural network. Select a neuron or connection; drag to pan and use the mouse wheel to zoom."
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerLeave={() => setHovered(null)}
        onWheel={wheel}
      />
      <div className="obs-canvas-controls" aria-label="Network view controls">
        <button title="Zoom in" aria-label="Zoom in" onClick={() => zoom(1.2)}>
          <Plus size={15} />
        </button>
        <button title="Zoom out" aria-label="Zoom out" onClick={() => zoom(0.84)}>
          <Minus size={15} />
        </button>
        <button
          title="Reset view"
          aria-label="Reset view"
          onClick={() => setView({ zoom: 1, panX: 0, panY: 0 })}
        >
          <Maximize2 size={14} />
        </button>
      </div>
    </div>
  );
}

function NetworkExplorer({
  data,
  models,
  onSampleChange,
}: {
  data: NetworkData;
  models: ModelSummary[];
  onSampleChange: (index: number) => void;
}) {
  const [selected, setSelected] = useState<
    | { type: 'neuron'; layer: number; index: number }
    | { type: 'connection'; layer: number; from: number; to: number; weight: number }
  >({ type: 'neuron', layer: 3, index: 0 });
  const [layer, setLayer] = useState(1);
  const [technical, setTechnical] = useState(false);
  const [animationStage, setAnimationStage] = useState<number | null>(null);
  const [animationProgress, setAnimationProgress] = useState(0);
  const timer = useRef<number | null>(null);
  const interval = useRef<number | null>(null);
  const [compareId, setCompareId] = useState('');
  const comparison = useQuery({
    queryKey: ['observatory-network', compareId, data.sample.index],
    queryFn: () =>
      api<NetworkData>(
        `/arena/observatory/models/${compareId}/network?sample_index=${data.sample.index}`,
      ),
    enabled: !!compareId,
    retry: false,
  });
  const compatible = models.filter(
    (candidate) =>
      candidate.model_id !== data.model.model_id &&
      candidate.dataset_id === data.model.dataset_id &&
      candidate.label_target === data.model.label_target,
  );
  useEffect(
    () => () => {
      if (timer.current != null) window.clearTimeout(timer.current);
      if (interval.current != null) window.clearInterval(interval.current);
    },
    [],
  );
  const playSignal = () => {
    if (timer.current != null) window.clearTimeout(timer.current);
    if (interval.current != null) window.clearInterval(interval.current);
    let stage = 0;
    setAnimationStage(0);
    setAnimationProgress(0);
    const began = performance.now();
    interval.current = window.setInterval(() => {
      const t = Math.min(1, (performance.now() - began - stage * 780) / 780);
      setAnimationProgress(t);
      if (t >= 1 && stage < 2) {
        stage += 1;
        setAnimationStage(stage);
        setAnimationProgress(0);
      }
    }, 35);
    timer.current = window.setTimeout(() => {
      if (interval.current != null) window.clearInterval(interval.current);
      interval.current = null;
      setAnimationStage(null);
      setAnimationProgress(0);
    }, 2340);
  };
  const stopSignal = () => {
    if (timer.current != null) window.clearTimeout(timer.current);
    if (interval.current != null) window.clearInterval(interval.current);
    timer.current = null;
    interval.current = null;
    setAnimationStage(null);
    setAnimationProgress(0);
  };
  const selectedDescription =
    selected.type === 'connection'
      ? 'This connection helps transfer information between two neurons. Its strength is determined by a value learned during training.'
      : selected.layer === 0
        ? 'This node is one of the saved values the model receives. Before the network uses it, MIDAS applies the same scaling recorded during training.'
        : selected.layer === 3
          ? `This output is the model’s estimated probability that an example will ${labelTarget(data.model.label_target)}.`
          : 'This neuron combines signals from the layer before it. Its activity is calculated from this saved example and the model’s actual learned weights.';
  const selectedTechnical =
    selected.type === 'connection'
      ? `Weight ${selected.weight.toPrecision(6)} · source value ${number(data.activations[selected.layer]?.[selected.from], 5)} · target activation ${number(data.activations[selected.layer + 1]?.[selected.to], 5)}`
      : selected.layer === 0
        ? `${data.input.features[selected.index]?.name ?? 'Input'} · observed ${number(data.input.features[selected.index]?.raw_value, 5)} · standardized ${number(data.activations[0]?.[selected.index], 5)}`
        : `Layer ${selected.layer + 1} · neuron ${selected.index + 1} · activation ${number(data.activations[selected.layer]?.[selected.index], 5)}`;
  return (
    <section className="obs-network-view">
      <div className="obs-toolbar">
        <div className="obs-select-field">
          <label htmlFor="obs-example">Saved validation example</label>
          <select
            id="obs-example"
            value={data.sample.index}
            onChange={(event) => onSampleChange(Number(event.target.value))}
          >
            {Array.from({ length: Math.min(data.dataset.validation_count, 12) }, (_, index) => (
              <option value={index} key={index}>
                Example {String(index + 1).padStart(2, '0')}
              </option>
            ))}
          </select>
        </div>
        <div className="obs-select-field obs-compare-select">
          <label htmlFor="obs-compare">Compare a matching model</label>
          <select
            id="obs-compare"
            value={compareId}
            onChange={(event) => setCompareId(event.target.value)}
            disabled={!compatible.length}
          >
            <option value="">No comparison</option>
            {compatible.slice(0, 24).map((item) => (
              <option key={item.model_id} value={item.model_id}>
                {item.model_id.slice(-8)} · {item.state}
              </option>
            ))}
          </select>
        </div>
        <button
          className="obs-action-button obs-signal-button"
          onClick={animationStage == null ? playSignal : stopSignal}
        >
          {animationStage == null ? <Play size={15} /> : <Pause size={15} />}
          {animationStage == null ? 'Play this signal' : 'Pause signal'}
        </button>
      </div>
      <div className="obs-network-grid">
        <div className="obs-network-stage">
          <div className="obs-network-stage-head">
            <div>
              <span className="obs-section-kicker">
                <span className="obs-pulse-dot" />
                {data.model.state === 'EVALUATED' ? 'SAVED MODEL' : 'TRAINED MODEL'}
              </span>
              <h2>
                {data.model.architecture.join('  /  ')} <span>neurons by layer</span>
              </h2>
            </div>
            <div className="obs-legend">
              <span>
                <i className="positive" />
                Positive learned weight
              </span>
              <span>
                <i className="negative" />
                Negative learned weight
              </span>
            </div>
          </div>
          <NetworkCanvas
            data={data}
            selected={selected}
            onSelect={(selection) => {
              setSelected(selection);
              if (selection.type === 'neuron') setLayer(selection.layer);
              else setLayer(selection.layer);
            }}
            activeLayer={layer}
            animationStage={animationStage}
            animationProgress={animationProgress}
          />
          <div className="obs-layer-controls" aria-label="Select a network layer">
            {stageNames.map((name, index) => (
              <button
                key={name}
                className={index === layer ? 'active' : ''}
                onClick={() => {
                  setLayer(index);
                  setSelected({ type: 'neuron', layer: index, index: index === 3 ? 0 : 0 });
                }}
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                {name}
                <small>{data.model.architecture[index]}</small>
              </button>
            ))}
          </div>
          <div className="obs-network-note">
            <CircleHelp size={14} />A completed forward pass uses the selected saved example and
            this model’s verified weights. Moving signals replay those computed values; they are not
            a live training process.
          </div>
        </div>
        <aside className="obs-network-inspector">
          <div className="obs-inspector-topline">
            <span>MODEL INSPECTOR</span>
            <span className="obs-verified">
              <ShieldCheck size={13} />
              WEIGHTS VERIFIED
            </span>
          </div>
          <div className="obs-inspector-output">
            <span>Model estimate</span>
            <strong>{percent(data.prediction.probability)}</strong>
            <div className="obs-estimate-bar">
              <i style={{ width: percent(data.prediction.probability) }} />
            </div>
            <p>
              Estimated chance of “{labelTarget(data.model.label_target)}” in the saved research
              task.
            </p>
          </div>
          <div className="obs-inspector-body">
            <span className="obs-section-kicker">
              {selected.type === 'connection'
                ? 'CONNECTION'
                : `LAYER ${selected.layer + 1} · ${stageNames[selected.layer]}`}
            </span>
            <h3>
              {selected.type === 'connection'
                ? `Neuron ${selected.from + 1} → ${selected.to + 1}`
                : selected.layer === 0
                  ? (data.input.features[selected.index]?.name ?? 'Input feature')
                  : selected.layer === 3
                    ? 'Estimated probability'
                    : `Neuron ${selected.index + 1}`}
            </h3>
            <p>{selectedDescription}</p>
            {technical && <code>{selectedTechnical}</code>}
            <button className="obs-text-button" onClick={() => setTechnical((value) => !value)}>
              {technical ? 'Hide technical detail' : 'Show actual values'}{' '}
              <ArrowUpRight size={13} />
            </button>
          </div>
          <div className="obs-inspector-sample">
            <div className="obs-sample-orbit">
              <Database size={18} />
              <span />
            </div>
            <div>
              <strong>
                {data.sample.family.replaceAll('_', ' ')} · {data.sample.execution_model}
              </strong>
              <small>
                Validation example {data.sample.index + 1} ·{' '}
                {data.dataset.provenance.replaceAll('_', ' ').toLowerCase()}
              </small>
            </div>
          </div>
          {compareId && (
            <div className="obs-compare-result">
              <span>SECOND MODEL · SAME SAVED EXAMPLE</span>
              {comparison.isPending ? (
                <small>Computing the matching forward pass…</small>
              ) : comparison.data ? (
                <>
                  <strong>{percent(comparison.data.prediction.probability)}</strong>
                  <small>Model estimate · {compareId.slice(-8)}</small>
                  <em>
                    {comparison.data.prediction.probability > data.prediction.probability
                      ? 'Higher'
                      : comparison.data.prediction.probability < data.prediction.probability
                        ? 'Lower'
                        : 'Same'}{' '}
                    estimate than the selected model
                  </em>
                </>
              ) : (
                <small>{comparison.error?.message ?? 'This matching model is unavailable.'}</small>
              )}
            </div>
          )}
          <div className="obs-data-boundary">
            <ShieldCheck size={15} />
            The saved dataset is {data.dataset.provenance.replaceAll('_', ' ').toLowerCase()}. A
            model estimate is not a verified outcome or a real-world result.
          </div>
        </aside>
      </div>
    </section>
  );
}

function LearningView({ data }: { data: ObservatoryData }) {
  const savedRuns = data.training_runs.filter((run) => run.model_id && run.has_learning_history);
  const [modelId, setModelId] = useState(savedRuns[0]?.model_id ?? '');
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const currentRun = savedRuns.find((run) => run.model_id === modelId) ?? savedRuns[0];
  const model = useQuery({
    queryKey: ['observatory-learning', currentRun?.model_id],
    queryFn: () => api<ModelDetail>(`/arena/models/${currentRun?.model_id}`),
    enabled: !!currentRun?.model_id,
    retry: false,
  });
  const curves = model.data?.curves ?? [];
  const mlpCurves = curves.filter(
    (row) => Number.isFinite(row.training_loss) && Number.isFinite(row.validation_loss),
  );
  const ppoCurves = curves.filter((row) => Number.isFinite(row.episode_return));
  const series = mlpCurves.length ? mlpCurves : ppoCurves;
  const maxIndex = Math.max(0, series.length - 1);
  const point = series[Math.min(cursor, maxIndex)];
  const maxValue = mlpCurves.length
    ? Math.max(...mlpCurves.flatMap((row) => [row.training_loss ?? 0, row.validation_loss ?? 0]))
    : Math.max(1, ...ppoCurves.map((row) => row.episode_return ?? 0));
  const minValue = mlpCurves.length
    ? 0
    : Math.min(0, ...ppoCurves.map((row) => row.episode_return ?? 0));
  const x = (index: number) => 48 + (series.length <= 1 ? 0 : (index / (series.length - 1)) * 824);
  const y = (value: number) =>
    218 - ((value - minValue) / Math.max(0.00001, maxValue - minValue)) * 174;
  const path = (key: 'training_loss' | 'validation_loss' | 'episode_return') =>
    series.map((row, index) => `${index ? 'L' : 'M'} ${x(index)} ${y(row[key] ?? 0)}`).join(' ');
  useEffect(() => {
    if (!playing || !series.length) return;
    const timer = window.setInterval(
      () =>
        setCursor((index) => {
          if (index >= maxIndex) {
            setPlaying(false);
            return 0;
          }
          return index + 1;
        }),
      620,
    );
    return () => window.clearInterval(timer);
  }, [playing, maxIndex, series.length]);
  useEffect(() => {
    setCursor(0);
    setPlaying(false);
  }, [modelId]);
  const firstValidation = mlpCurves[0]?.validation_loss;
  const lastValidation = mlpCurves[mlpCurves.length - 1]?.validation_loss;
  const trainEnd = mlpCurves[mlpCurves.length - 1]?.training_loss;
  const validationRose =
    firstValidation != null && lastValidation != null && lastValidation > firstValidation * 1.04;
  const overfitSignal = validationRose && trainEnd != null && trainEnd < (lastValidation ?? 0);

  return (
    <section className="obs-learning-view">
      <div className="obs-learning-head">
        <div>
          <span className="obs-section-kicker">
            <Activity size={14} /> SAVED LEARNING RECORDS
          </span>
          <h2>Watch what changed during training.</h2>
          <p>
            Each line comes from a recorded training run. Replay moves through saved measurements;
            it does not replay unsaved model weights.
          </p>
        </div>
        <div className="obs-select-field obs-learning-select">
          <label htmlFor="obs-training-run">Choose a training run</label>
          <select
            id="obs-training-run"
            value={currentRun?.model_id ?? ''}
            onChange={(event) => setModelId(event.target.value)}
            disabled={!savedRuns.length}
          >
            {savedRuns.map((run) => (
              <option key={run.model_id} value={run.model_id}>
                {run.family.toUpperCase()} · {run.model_id?.slice(-8)} · {run.state}
              </option>
            ))}
          </select>
        </div>
      </div>
      {data.active_training_records > 0 && (
        <div className="obs-active-training">
          <span className="obs-pulse-dot" />
          {data.active_training_records} training job{data.active_training_records === 1 ? '' : 's'}{' '}
          currently marked active in saved job records. Refreshing reads does not control or pause
          them.
        </div>
      )}
      {!savedRuns.length && (
        <div className="obs-empty-state">
          <Activity size={28} />
          <h3>No saved learning curve is available</h3>
          <p>
            Training runs that did not save intermediate measurements appear in the Research
            Universe without a made-up progress history.
          </p>
        </div>
      )}
      {savedRuns.length > 0 && model.isLoading && (
        <div className="obs-empty-state">Loading the saved training record…</div>
      )}
      {model.isError && (
        <div className="obs-empty-state">
          <h3>Training record unavailable</h3>
          <p>{model.error.message}</p>
        </div>
      )}
      {model.data && (
        <>
          <div className="obs-learning-summary">
            <div>
              <span>TRAINING RUN</span>
              <strong>{model.data.model_id.slice(-12)}</strong>
              <small>
                {model.data.family.toUpperCase()} · {formatTime(model.data.created_at)}
              </small>
            </div>
            <div>
              <span>MEASURED STEPS</span>
              <strong>
                {mlpCurves.length ? `${mlpCurves.length} epochs` : `${ppoCurves.length} episodes`}
              </strong>
              <small>{model.data.state} · saved on the training path</small>
            </div>
            <div>
              <span>VALIDATION SCORE</span>
              <strong>
                {model.data.validation?.brier == null
                  ? 'Not recorded'
                  : number(model.data.validation.brier, 4)}
              </strong>
              <small>
                {model.data.validation?.brier == null
                  ? 'This run has no held-out score'
                  : `${model.data.validation.rows ?? 'Saved'} validation examples · lower Brier score is closer on average`}
              </small>
            </div>
            <div>
              <span>TRAINING SOURCE</span>
              <strong>{model.data.dataset_id.slice(-10)}</strong>
              <small>
                {model.data.label_target
                  ? `Target: ${labelTarget(model.data.label_target)}`
                  : 'Synthetic simulation data'}
              </small>
            </div>
          </div>
          <div className="obs-learning-chart-card">
            <div className="obs-chart-heading">
              <div>
                <span className="obs-section-kicker">
                  {mlpCurves.length ? 'PREDICTION FIT' : 'EPISODE RESULTS'}
                </span>
                <h3>
                  {mlpCurves.length
                    ? 'The model’s outputs move closer to saved labels'
                    : 'Recorded reward across training episodes'}
                </h3>
                <p>
                  {mlpCurves.length
                    ? 'Lower loss means predictions better matched examples in this training run. Validation examples were kept separate from training.'
                    : 'Each point is a saved episode return. Training return is not an independent test of real-world behavior.'}
                </p>
              </div>
              <button
                className="obs-action-button"
                onClick={() => {
                  if (playing) {
                    setPlaying(false);
                    return;
                  }
                  if (cursor >= maxIndex) setCursor(0);
                  setPlaying(true);
                }}
                disabled={!series.length}
              >
                {playing ? <Pause size={15} /> : <Play size={15} />}
                {playing ? 'Pause replay' : 'Replay this run'}
              </button>
            </div>
            {series.length > 0 ? (
              <svg
                className="obs-learning-chart"
                viewBox="0 0 920 270"
                role="img"
                aria-label={
                  mlpCurves.length
                    ? 'Recorded training and validation loss by epoch'
                    : 'Recorded PPO episode return by training episode'
                }
              >
                <defs>
                  <linearGradient id="obsLossFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0" stopColor="#7fb5bd" stopOpacity=".19" />
                    <stop offset="1" stopColor="#7fb5bd" stopOpacity="0" />
                  </linearGradient>
                </defs>
                {[0, 1, 2, 3].map((line) => (
                  <g key={line}>
                    <line
                      x1="48"
                      x2="872"
                      y1={44 + line * 58}
                      y2={44 + line * 58}
                      stroke="#252e35"
                      strokeDasharray="3 6"
                    />
                    <text x="9" y={48 + line * 58}>
                      {number(maxValue - ((maxValue - minValue) * line) / 3, 2)}
                    </text>
                  </g>
                ))}
                {mlpCurves.length ? (
                  <>
                    <path
                      d={`${path('training_loss')} L ${x(series.length - 1)} 218 L ${x(0)} 218 Z`}
                      fill="url(#obsLossFill)"
                    />
                    <path
                      d={path('training_loss')}
                      fill="none"
                      stroke="#83b7c0"
                      strokeWidth="2.5"
                    />
                    <path
                      d={path('validation_loss')}
                      fill="none"
                      stroke="#d5b16c"
                      strokeWidth="2.2"
                      strokeDasharray="7 5"
                    />
                  </>
                ) : (
                  <path d={path('episode_return')} fill="none" stroke="#82c5a2" strokeWidth="2.5" />
                )}
                {point && (
                  <>
                    <line
                      x1={x(Math.min(cursor, maxIndex))}
                      x2={x(Math.min(cursor, maxIndex))}
                      y1="34"
                      y2="220"
                      stroke="#e6ddc4"
                      strokeDasharray="3 5"
                      opacity=".55"
                    />
                    <circle
                      cx={x(Math.min(cursor, maxIndex))}
                      cy={y((mlpCurves.length ? point.validation_loss : point.episode_return) ?? 0)}
                      r="5.5"
                      fill="#e3c88d"
                      stroke="#151b20"
                      strokeWidth="3"
                    />
                  </>
                )}
                <text x="48" y="250">
                  {mlpCurves.length ? 'Epoch 1' : 'First saved episode'}
                </text>
                <text x="872" y="250" textAnchor="end">
                  {mlpCurves.length ? `Epoch ${series.length}` : `${series.length} saved episodes`}
                </text>
              </svg>
            ) : (
              <div className="obs-empty-state">
                <h3>No intermediate measurements saved</h3>
                <p>
                  This model’s final result is recorded, but MIDAS did not save a curve that can be
                  replayed.
                </p>
              </div>
            )}
            {mlpCurves.length > 0 && (
              <div className="obs-chart-legend">
                <span>
                  <i className="train" />
                  Training examples
                </span>
                <span>
                  <i className="validation" />
                  Unseen validation examples
                </span>
                <b>
                  Epoch {point?.epoch ?? cursor + 1} / {series.length}
                </b>
              </div>
            )}
            {!mlpCurves.length && ppoCurves.length > 0 && (
              <div className="obs-chart-legend">
                <span>
                  <i className="episode" />
                  Episode return
                </span>
                <b>
                  Episode {cursor + 1} / {series.length}
                </b>
              </div>
            )}
            <input
              className="obs-scrubber"
              aria-label="Choose a saved training point"
              type="range"
              min={0}
              max={maxIndex}
              value={Math.min(cursor, maxIndex)}
              onChange={(event) => {
                setPlaying(false);
                setCursor(Number(event.target.value));
              }}
            />
            {mlpCurves.length > 0 && (
              <div className={`obs-learning-interpretation ${overfitSignal ? 'caution' : ''}`}>
                <Sparkles size={16} />
                <p>
                  {overfitSignal
                    ? 'The saved training loss continued to fall while validation loss rose. That is evidence this run fit its training examples better than its held-out examples near the end.'
                    : validationRose
                      ? 'Validation loss rose near the end of this saved curve. This run did not keep improving on its held-out examples throughout training.'
                      : 'The validation curve shows how the model performed on examples set aside during this run. This measure describes this dataset only.'}
                </p>
              </div>
            )}
          </div>
          <div className="obs-history-limit">
            <ShieldCheck size={15} />
            <p>
              <strong>What this replay can show:</strong> the recorded loss or episode values
              changed over time. <strong>What it cannot show:</strong> how every network connection
              changed, because intermediate weight snapshots were not saved for this run.
            </p>
          </div>
          {!!model.data.limitations?.length && (
            <details className="obs-limitations">
              <summary>Research limits and assumptions</summary>
              <ul>
                {model.data.limitations.slice(0, 8).map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}

function graphDescription(node: GraphNode) {
  if (node.kind === 'dataset')
    return 'A saved set of examples with an explicit target and partition. Models link here only when their saved manifest names this dataset.';
  if (node.kind === 'model')
    return `A saved ${node.family?.replaceAll('_', ' ') ?? 'research'} model. Its connected evaluations are recorded elsewhere in the research graph.`;
  if (node.kind === 'experiment')
    return 'A recorded comparison or evaluation. Results inherit the source, simulator, and uncertainty limits attached to its artifact.';
  if (node.kind === 'finding')
    return 'A written result produced or informed by the linked research artifacts. Open the related simulation or model to inspect evidence.';
  if (node.kind === 'director')
    return 'A bounded research sequence. Its links come from the artifacts named in its recorded steps.';
  if (node.kind === 'plan')
    return 'A saved research plan or schedule. The graph shows only the source and evidence references present in the record.';
  if (node.kind === 'training')
    return 'A training job record. Progress, when present, is the last saved progress value.';
  if (node.kind === 'observation')
    return 'A public observation artifact. It is separate from generated Arena simulation evidence.';
  return 'A saved research artifact. Select a linked item to follow its documented relationship.';
}

function ResearchUniverse({
  data,
  onExploreModel,
  onExploreSimulation,
}: {
  data: ObservatoryData;
  onExploreModel: (id: string) => void;
  onExploreSimulation: (id: string) => void;
}) {
  const [selectedId, setSelectedId] = useState('');
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 });
  const [drag, setDrag] = useState<{
    startX: number;
    startY: number;
    baseX: number;
    baseY: number;
    moved: boolean;
  } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const counts = data.bounded.artifact_counts_by_type;
  const graphKey = `${data.graph.nodes.map((node) => node.id).join(',')}|${data.graph.edges.map((edge) => `${edge.source}>${edge.target}`).join(',')}`;
  const cachedLayout = useRef<{
    key: string;
    positions: Map<string, { x: number; y: number; ax: number; ay: number }>;
  } | null>(null);
  const layout = useMemo(() => {
    if (cachedLayout.current?.key === graphKey) return cachedLayout.current.positions;
    const positions = graphLayout(data.graph.nodes, data.graph.edges);
    cachedLayout.current = { key: graphKey, positions };
    return positions;
  }, [data.graph.edges, data.graph.nodes, graphKey]);
  const selected = data.graph.nodes.find((node) => node.id === selectedId) ?? data.graph.nodes[0];
  const dimensions = { width: 1080, height: 680 };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(canvas.clientWidth * ratio);
    canvas.height = Math.round(canvas.clientHeight * ratio);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const sx = canvas.clientWidth / dimensions.width;
    const sy = canvas.clientHeight / dimensions.height;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    ctx.fillStyle = '#0b1016';
    ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(sx * view.zoom, sy * view.zoom);
    ctx.strokeStyle = 'rgba(138,157,174,.045)';
    ctx.lineWidth = 1;
    for (let x = 0; x < dimensions.width; x += 42) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, dimensions.height);
      ctx.stroke();
    }
    for (let y = 0; y < dimensions.height; y += 42) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(dimensions.width, y);
      ctx.stroke();
    }
    const clusterHeads: [string, number, number][] = [
      ['DATASETS', 78, 76],
      ['MODELS', 308, 75],
      ['EVALUATIONS', 590, 76],
      ['FINDINGS', 878, 105],
      ['RESEARCH PLANS', 595, 654],
      ['TRAINING', 78, 652],
    ];
    ctx.font = '600 9px Inter, sans-serif';
    ctx.fillStyle = 'rgba(143, 159, 165, .42)';
    for (const [label, x, y] of clusterHeads) ctx.fillText(label, x, y);
    for (const edge of data.graph.edges) {
      const source = layout.get(edge.source);
      const target = layout.get(edge.target);
      if (!source || !target) continue;
      const linked = edge.source === selectedId || edge.target === selectedId;
      const related = selected && (edge.source === selected.id || edge.target === selected.id);
      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.quadraticCurveTo(
        (source.x + target.x) / 2,
        (source.y + target.y) / 2 - 8,
        target.x,
        target.y,
      );
      ctx.strokeStyle = linked
        ? 'rgba(220,193,139,.72)'
        : related
          ? 'rgba(196,178,141,.42)'
          : 'rgba(129,149,165,.11)';
      ctx.lineWidth = linked ? 1.6 : 0.72;
      ctx.stroke();
      if (linked) {
        ctx.fillStyle = '#e7cf9f';
        ctx.beginPath();
        ctx.arc((source.x + target.x) / 2, (source.y + target.y) / 2 - 4, 2.1, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    for (const node of data.graph.nodes) {
      const point = layout.get(node.id);
      if (!point) continue;
      const color = nodeColor(node.kind);
      const focused = node.id === selectedId;
      const radius = focused
        ? 7.4
        : node.kind === 'training' && ['RUNNING', 'QUEUED'].includes(node.state)
          ? 6.4
          : node.kind === 'model'
            ? 4.4
            : node.kind === 'finding'
              ? 4
              : 3.3;
      if (focused) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 17, 0, Math.PI * 2);
        ctx.fillStyle = `${color}13`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(point.x, point.y, 12, 0, Math.PI * 2);
        ctx.strokeStyle = `${color}66`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.shadowBlur = focused ? 16 : 4;
      ctx.shadowColor = `${color}66`;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    const recent = [...data.graph.nodes]
      .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0))
      .slice(0, 4);
    const labelCandidates = [selected, ...recent].filter(
      (node, index, list): node is GraphNode =>
        !!node && list.findIndex((item) => item?.id === node.id) === index,
    );
    const labelBounds: { left: number; right: number; top: number; bottom: number }[] = [];
    for (const node of labelCandidates) {
      const point = layout.get(node.id);
      if (!point) continue;
      const focused = node.id === selectedId;
      const label = node.title.slice(0, 35);
      ctx.font = focused ? '600 10px Inter, sans-serif' : '10px Inter, sans-serif';
      ctx.textAlign = point.x > dimensions.width * 0.78 ? 'right' : 'left';
      const textWidth = ctx.measureText(label).width;
      const x = point.x + (ctx.textAlign === 'right' ? -9 : 9);
      const y = point.y - 8;
      const bounds = {
        left: ctx.textAlign === 'right' ? x - textWidth : x,
        right: ctx.textAlign === 'right' ? x : x + textWidth,
        top: y - 10,
        bottom: y + 3,
      };
      if (
        !focused &&
        labelBounds.some(
          (other) =>
            bounds.left < other.right + 8 &&
            bounds.right + 8 > other.left &&
            bounds.top < other.bottom + 5 &&
            bounds.bottom + 5 > other.top,
        )
      )
        continue;
      labelBounds.push(bounds);
      ctx.fillStyle = focused ? '#e2e6e9' : '#8e9aa8';
      ctx.fillText(label, x, y);
    }
    ctx.restore();
  }, [
    data.graph.edges,
    data.graph.nodes,
    dimensions.height,
    dimensions.width,
    layout,
    selected,
    selectedId,
    view,
  ]);

  const pointAt = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    return {
      x:
        (event.clientX - rect.left - view.x) /
        ((canvas.clientWidth / dimensions.width) * view.zoom),
      y:
        (event.clientY - rect.top - view.y) /
        ((canvas.clientHeight / dimensions.height) * view.zoom),
    };
  };
  const pointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    setDrag({
      startX: event.clientX,
      startY: event.clientY,
      baseX: view.x,
      baseY: view.y,
      moved: false,
    });
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const pointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!drag) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (drag.moved) setView((old) => ({ ...old, x: drag.baseX + dx, y: drag.baseY + dy }));
  };
  const pointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (drag?.moved) {
      setDrag(null);
      return;
    }
    const point = pointAt(event);
    setDrag(null);
    if (!point) return;
    let found: { node: GraphNode; distance: number } | null = null;
    for (const node of data.graph.nodes) {
      const p = layout.get(node.id);
      if (!p) continue;
      const distance = Math.hypot(point.x - p.x, point.y - p.y);
      if (distance < 18 && (!found || distance < found.distance)) found = { node, distance };
    }
    if (found) setSelectedId(found.node.id);
  };
  const zoom = (amount: number) =>
    setView((old) => ({ ...old, zoom: Math.max(0.6, Math.min(2.5, old.zoom * amount)) }));
  const wheel = (event: ReactWheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setView((old) => {
      const nextZoom = Math.max(0.6, Math.min(2.5, old.zoom * (event.deltaY < 0 ? 1.12 : 0.89)));
      const scale = nextZoom / old.zoom;
      return { zoom: nextZoom, x: x - (x - old.x) * scale, y: y - (y - old.y) * scale };
    });
  };
  return (
    <section className="obs-universe-view">
      <div className="obs-universe-head">
        <div>
          <span className="obs-section-kicker">
            <Waypoints size={15} /> RESEARCH PROVENANCE
          </span>
          <h2>Follow the evidence through MIDAS.</h2>
          <p>
            Every line has a source in a saved artifact: a dataset, model, evaluation, plan, or
            result.
          </p>
        </div>
        <div className="obs-universe-count">
          <strong>{data.graph.nodes.length}</strong>
          <span>connected artifacts</span>
          <i />
          <strong>{data.graph.edges.length}</strong>
          <span>recorded links</span>
        </div>
      </div>
      <div className="obs-universe-frame">
        <div className="obs-universe-map">
          <canvas
            ref={canvasRef}
            aria-label="Interactive map of Arena research artifacts and their recorded relationships; drag to pan and scroll to zoom"
            onPointerDown={pointerDown}
            onPointerMove={pointerMove}
            onPointerUp={pointerUp}
            onWheel={wheel}
          />
          <div className="obs-universe-controls">
            <button aria-label="Zoom in" title="Zoom in" onClick={() => zoom(1.2)}>
              <Plus size={14} />
            </button>
            <button aria-label="Zoom out" title="Zoom out" onClick={() => zoom(0.84)}>
              <Minus size={14} />
            </button>
            <button
              aria-label="Reset universe view"
              title="Reset view"
              onClick={() => setView({ zoom: 1, x: 0, y: 0 })}
            >
              <RotateCcw size={14} />
            </button>
          </div>
          <div className="obs-map-hint">
            <Compass size={13} />
            Drag to explore · scroll to zoom · select any point
          </div>
          <div className="obs-map-legend">
            {[
              ['dataset', 'Datasets'],
              ['model', 'Models'],
              ['experiment', 'Evaluations'],
              ['finding', 'Findings'],
              ['plan', 'Plans'],
              ['director', 'Directors'],
            ].map(([kind, label]) => (
              <span key={kind}>
                <i style={{ background: nodeColor(kind) }} />
                {label}
              </span>
            ))}
          </div>
        </div>
        <aside className="obs-universe-inspector">
          {selected ? (
            <>
              <span className="obs-section-kicker">
                <i className="obs-node-dot" style={{ background: nodeColor(selected.kind) }} />
                {selected.kind.replaceAll('_', ' ').toUpperCase()}
              </span>
              <h3>{selected.title}</h3>
              <p className="obs-node-summary">{selected.summary}</p>
              <div className="obs-node-status">
                <span>{selected.state}</span>
                <small>{formatTime(selected.created_at)}</small>
              </div>
              <p className="obs-node-explanation">{graphDescription(selected)}</p>
              {selected.kind === 'training' && selected.progress && (
                <div className="obs-progress">
                  <span>Last saved progress</span>
                  <strong>
                    {selected.progress.done ?? '—'} / {selected.progress.total ?? '—'}{' '}
                    {selected.progress.unit ?? 'steps'}
                  </strong>
                  <i>
                    <b
                      style={{
                        width: `${selected.progress.total ? Math.min(100, ((selected.progress.done ?? 0) / selected.progress.total) * 100) : 0}%`,
                      }}
                    />
                  </i>
                </div>
              )}
              <code className="obs-node-id">{selected.identity}</code>
              <div className="obs-node-actions">
                {selected.kind === 'model' && selected.family === 'mlp' && (
                  <button
                    className="obs-action-button"
                    onClick={() => onExploreModel(selected.identity)}
                  >
                    <Network size={14} />
                    Explore network
                  </button>
                )}
                {selected.kind === 'experiment' &&
                  data.simulations.some((item) => item.tournament_id === selected.identity) && (
                    <button
                      className="obs-action-button"
                      onClick={() => onExploreSimulation(selected.identity)}
                    >
                      <AudioLines size={14} />
                      Inspect simulation
                    </button>
                  )}
              </div>
            </>
          ) : (
            <div className="obs-empty-state">
              <Layers3 size={28} />
              <h3>Select an artifact</h3>
              <p>Choose a point in the universe to read its saved description.</p>
            </div>
          )}
        </aside>
      </div>
      <div className="obs-universe-footer">
        <div className="obs-kind-counts">
          {[
            ['datasets', 'Datasets'],
            ['models', 'Models'],
            ['tournaments', 'Evaluations'],
            ['findings', 'Findings'],
            ['directors', 'Directors'],
          ].map(([kind, label]) => (
            <span key={kind}>
              <b>{counts[kind] ?? 0}</b>
              {label}
            </span>
          ))}
        </div>
        <p>
          {data.bounded.truncated
            ? 'This view reached its artifact reading bound. Some saved artifacts may be outside the displayed window.'
            : 'The graph is a bounded read of saved Arena artifacts. Public observations and generated simulations remain distinct evidence classes.'}
        </p>
      </div>
    </section>
  );
}

function SimulationView({ data, initialId }: { data: ObservatoryData; initialId?: string }) {
  const options = data.simulations;
  const [tournamentId, setTournamentId] = useState(initialId || options[0]?.tournament_id || '');
  const [rowId, setRowId] = useState('');
  const [eventIndex, setEventIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const details = useQuery({
    queryKey: ['observatory-tournament', tournamentId],
    queryFn: () => api<TournamentDetail>(`/arena/tournaments/${tournamentId}`),
    enabled: !!tournamentId,
    retry: false,
  });
  const rows = useQuery({
    queryKey: ['observatory-tournament-rows', tournamentId],
    queryFn: () =>
      api<{ rows: TournamentRow[]; total: number }>(
        `/arena/tournaments/${tournamentId}/rows?offset=0&limit=40`,
      ),
    enabled: !!tournamentId,
    retry: false,
  });
  const selectedRow =
    rows.data?.rows.find((row) => row.id === rowId) ??
    rows.data?.rows.find((row) => row.policy !== 'no_trade') ??
    rows.data?.rows[0];
  const selectedEvaluation = options.find((item) => item.tournament_id === tournamentId);
  const replay = useQuery({
    queryKey: ['observatory-replay', tournamentId, selectedRow?.id],
    queryFn: () => api<ReplayData>(`/arena/tournaments/${tournamentId}/replay/${selectedRow?.id}`),
    enabled: !!tournamentId && !!selectedRow?.id,
    retry: false,
  });
  const journal = replay.data?.result.journal ?? [];
  const current = journal[Math.min(eventIndex, Math.max(0, journal.length - 1))];
  const equity = journal.map((event) => Number(event.after.equity ?? event.after.available ?? 0));
  const equityMin = Math.min(0, ...equity);
  const equityMax = Math.max(1, ...equity);
  const path = equity
    .map(
      (value, index) =>
        `${index ? 'L' : 'M'} ${50 + (equity.length <= 1 ? 0 : (index / (equity.length - 1)) * 840)} ${190 - ((value - equityMin) / Math.max(0.01, equityMax - equityMin)) * 150}`,
    )
    .join(' ');
  useEffect(() => {
    setRowId('');
    setEventIndex(0);
    setPlaying(false);
  }, [tournamentId]);
  useEffect(() => {
    if (!playing || journal.length === 0) return;
    const timer = window.setInterval(
      () =>
        setEventIndex((index) => {
          if (index >= journal.length - 1) {
            setPlaying(false);
            return 0;
          }
          return index + 1;
        }),
      720,
    );
    return () => window.clearInterval(timer);
  }, [journal.length, playing]);
  const decision = replay.data?.decisions[0];
  const decisionObservation = decision?.observation ?? [];
  const inputSchema = selectedEvaluation?.feature_schema ?? [];
  const schemaMatches =
    inputSchema.length > 0 &&
    decisionObservation.length >= inputSchema.length &&
    decisionObservation.length <= inputSchema.length + 1;
  const portfolioValue = current
    ? Number(current.after.equity ?? current.after.available ?? 0)
    : undefined;
  const synthetic = details.data?.evaluation_design !== 'OBSERVED_PUBLIC';

  return (
    <section className="obs-simulation-view">
      <div className="obs-simulation-head">
        <div>
          <span className="obs-section-kicker">
            <AudioLines size={15} /> RECORDED DECISION REPLAY
          </span>
          <h2>Step through a saved simulation.</h2>
          <p>
            Inspect what the model saw, what policy it selected, and how the simulator recorded the
            result.
          </p>
        </div>
        <div className="obs-select-field obs-simulation-select">
          <label htmlFor="obs-simulation">Choose an evaluation</label>
          <select
            id="obs-simulation"
            value={tournamentId}
            onChange={(event) => setTournamentId(event.target.value)}
          >
            {options.slice(0, 60).map((item) => (
              <option key={item.tournament_id} value={item.tournament_id}>
                {item.evaluation_design?.replaceAll('_', ' ') ?? 'Saved evaluation'} ·{' '}
                {item.tournament_id.slice(-8)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {synthetic && (
        <div className="obs-simulation-boundary">
          <ShieldCheck size={16} />
          <p>
            <strong>Synthetic Arena simulation.</strong> Orders, fills, and outcomes shown here were
            generated inside MIDAS. They are not public market events or real trades, and a
            simulated result does not establish profitability.
          </p>
        </div>
      )}
      {!options.length && (
        <div className="obs-empty-state">
          <AudioLines size={28} />
          <h3>No recorded simulation to replay</h3>
          <p>A replay appears after an Arena evaluation stores its scenario events.</p>
        </div>
      )}
      {details.isLoading && <div className="obs-empty-state">Loading the saved evaluation…</div>}
      {details.isError && (
        <div className="obs-empty-state">
          <h3>Evaluation unavailable</h3>
          <p>{details.error.message}</p>
        </div>
      )}
      {details.data && (
        <>
          <div className="obs-sim-summary">
            <div>
              <span>SOURCE SCENARIOS</span>
              <strong>{details.data.base_episodes ?? '—'}</strong>
              <small>Repeated variants share underlying scenarios</small>
            </div>
            <div>
              <span>RECORDED VARIANTS</span>
              <strong>{details.data.variants ?? '—'}</strong>
              <small>Different policies or assumed execution</small>
            </div>
            <div>
              <span>EVALUATION TYPE</span>
              <strong>
                {details.data.evaluation_design?.replaceAll('_', ' ') ?? 'Saved research'}
              </strong>
              <small>
                {details.data.economically_verified
                  ? 'Economic verification recorded'
                  : 'Economic performance not verified'}
              </small>
            </div>
            <div>
              <span>CONCLUSION</span>
              <strong className="obs-conclusion">
                {details.data.conclusion ?? 'Read the recorded results'}
              </strong>
            </div>
          </div>
          {details.data.leaderboard?.length ? (
            <div className="obs-leaderboard">
              <div className="obs-chart-heading">
                <div>
                  <span className="obs-section-kicker">POLICY COMPARISON</span>
                  <h3>Recorded results under this simulator setup</h3>
                  <p>
                    Each result uses the same evaluation’s stated assumptions and evidence limits.
                  </p>
                </div>
              </div>
              <div className="obs-rank-list">
                {details.data.leaderboard.slice(0, 5).map((item, index) => (
                  <div key={item.policy} className="obs-rank-row">
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>{item.policy}</strong>
                    <i>
                      <b
                        style={{
                          width: `${Math.max(4, Math.min(100, ((item.score - Math.min(...details.data!.leaderboard!.map((row) => row.score))) / Math.max(0.0001, Math.max(...details.data!.leaderboard!.map((row) => row.score)) - Math.min(...details.data!.leaderboard!.map((row) => row.score)))) * 100))}%`,
                        }}
                      />
                    </i>
                    <small>
                      score {number(item.score, 2)} · mean virtual P&L {number(item.mean_pnl, 2)}
                    </small>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
      {rows.isError && (
        <div className="obs-empty-state">
          <h3>Saved scenarios unavailable</h3>
          <p>{rows.error.message}</p>
        </div>
      )}
      {rows.data && (
        <div className="obs-sim-replay-card">
          <div className="obs-replay-head">
            <div>
              <span className="obs-section-kicker">
                <GitBranch size={14} /> ONE SAVED SCENARIO
              </span>
              <h3>
                {selectedRow
                  ? `${selectedRow.family.replaceAll('_', ' ')} · ${selectedRow.execution_model}`
                  : 'Choose a scenario'}
              </h3>
            </div>
            <div className="obs-select-field obs-row-select">
              <label htmlFor="obs-row">Policy replay</label>
              <select
                id="obs-row"
                value={selectedRow?.id ?? ''}
                onChange={(event) => {
                  setRowId(event.target.value);
                  setEventIndex(0);
                }}
              >
                {rows.data.rows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.policy} · {row.family} · {row.execution_model}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {replay.isLoading && (
            <div className="obs-empty-state">Loading immutable replay events…</div>
          )}
          {replay.isError && (
            <div className="obs-empty-state">
              <h3>This scenario has no available replay</h3>
              <p>{replay.error.message} Select another saved scenario to continue.</p>
            </div>
          )}
          {replay.data && (
            <>
              <div className="obs-replay-content">
                <div className="obs-replay-chart-area">
                  <div className="obs-current-event">
                    <div>
                      <span>
                        EVENT {String(eventIndex + 1).padStart(2, '0')} / {journal.length}
                      </span>
                      <strong>{current?.kind.replaceAll('_', ' ') ?? 'Saved state'}</strong>
                      <small>
                        {current
                          ? new Date(current.time_ms).toLocaleTimeString()
                          : 'Replay position'}
                      </small>
                    </div>
                    <div>
                      <span>SIMULATED EQUITY</span>
                      <strong>
                        {portfolioValue == null ? '—' : `${number(portfolioValue, 2)} virtual USD`}
                      </strong>
                    </div>
                  </div>
                  <svg
                    className="obs-equity-chart"
                    viewBox="0 0 920 240"
                    role="img"
                    aria-label="Recorded simulated portfolio equity through replay events"
                  >
                    <defs>
                      <linearGradient id="obsEquityFill" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0" stopColor="#79bf9e" stopOpacity=".22" />
                        <stop offset="1" stopColor="#79bf9e" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <line
                      x1="50"
                      x2="890"
                      y1="190"
                      y2="190"
                      stroke="#29343a"
                      strokeDasharray="3 6"
                    />
                    <path
                      d={`${path} L ${50 + (equity.length <= 1 ? 0 : ((equity.length - 1) / (equity.length - 1)) * 840)} 190 L 50 190 Z`}
                      fill="url(#obsEquityFill)"
                    />
                    <path d={path} fill="none" stroke="#82c4a1" strokeWidth="2.5" />
                    {current && (
                      <circle
                        cx={
                          50 + (journal.length <= 1 ? 0 : (eventIndex / (journal.length - 1)) * 840)
                        }
                        cy={
                          190 -
                          ((Number(current.after.equity ?? current.after.available ?? 0) -
                            equityMin) /
                            Math.max(0.01, equityMax - equityMin)) *
                            150
                        }
                        r="5"
                        fill="#e5ce9c"
                      />
                    )}
                    <text x="50" y="220">
                      Start
                    </text>
                    <text x="890" y="220" textAnchor="end">
                      End of simulation
                    </text>
                  </svg>
                  <div className="obs-replay-controls">
                    <button
                      className="obs-action-button"
                      onClick={() => {
                        if (playing) {
                          setPlaying(false);
                          return;
                        }
                        if (eventIndex >= journal.length - 1) setEventIndex(0);
                        setPlaying(true);
                      }}
                      disabled={journal.length < 2}
                    >
                      {playing ? <Pause size={15} /> : <Play size={15} />}
                      {playing ? 'Pause replay' : 'Play replay'}
                    </button>
                    <input
                      aria-label="Move through replay events"
                      type="range"
                      min={0}
                      max={Math.max(0, journal.length - 1)}
                      value={eventIndex}
                      onChange={(event) => {
                        setPlaying(false);
                        setEventIndex(Number(event.target.value));
                      }}
                    />
                    <span>
                      {eventIndex + 1} / {journal.length}
                    </span>
                  </div>
                </div>
                <aside className="obs-decision-card">
                  <span className="obs-section-kicker">WHAT THE POLICY DID</span>
                  <h3>
                    {decision?.explanation?.policy ?? selectedRow?.policy ?? 'Recorded decision'}
                  </h3>
                  <p>
                    {decision?.explanation?.reason ??
                      'The simulator recorded this policy decision.'}
                  </p>
                  <div className="obs-decision-line">
                    <span>Selected action</span>
                    <strong>
                      {decision?.requested_action ?? String(decision?.action ?? 'Not recorded')}
                    </strong>
                  </div>
                  <div className="obs-decision-line">
                    <span>Eligible by recorded check</span>
                    <strong>
                      {decision?.explanation?.mathematically_eligible == null
                        ? 'Not available'
                        : decision.explanation.mathematically_eligible
                          ? 'Yes'
                          : 'No'}
                    </strong>
                  </div>
                  <div className="obs-decision-line">
                    <span>Simulation result</span>
                    <strong>
                      {replay.data.result.passed
                        ? 'Replay checks passed'
                        : 'Replay checks did not pass'}
                    </strong>
                  </div>
                  <div className="obs-decision-pnl">
                    <span>Net simulated P&amp;L</span>
                    <strong>
                      {selectedRow?.metrics.net_simulated_pnl ?? '—'}
                      <small> virtual USD</small>
                    </strong>
                  </div>
                  <p className="obs-decision-caveat">
                    “Passed” describes saved simulation checks. It does not mean a real trade
                    succeeded.
                  </p>
                  {!!decisionObservation.length && (
                    <details className="obs-decision-inputs">
                      <summary>
                        What the policy received ({decisionObservation.length} values)
                      </summary>
                      <p>
                        These are the saved, scaled values supplied at this decision. Labels come
                        from the dataset linked to this evaluation; they are not raw prices or
                        public market facts.
                      </p>
                      <div className="obs-observation-list">
                        {decisionObservation.slice(0, 64).map((value, index) => {
                          const eligibilityFlag =
                            schemaMatches &&
                            decisionObservation.length === inputSchema.length + 1 &&
                            index === inputSchema.length;
                          const feature = inputSchema[index];
                          const title = eligibilityFlag
                            ? 'Proposal passed the saved eligibility check'
                            : schemaMatches && feature
                              ? (decisionFeatureLabels[feature] ?? feature.replaceAll('_', ' '))
                              : `Saved input ${String(index + 1).padStart(2, '0')}`;
                          return (
                            <div key={index}>
                              <span>{title}</span>
                              <code>
                                {eligibilityFlag ? (value === 1 ? 'Yes' : 'No') : number(value, 4)}
                              </code>
                            </div>
                          );
                        })}
                      </div>
                      {!schemaMatches && (
                        <small>
                          The replay did not include a matching feature schema, so values are shown
                          by saved position.
                        </small>
                      )}
                    </details>
                  )}
                </aside>
              </div>
              {replay.data.result.journal.length > 0 && (
                <details className="obs-event-details">
                  <summary>Read the saved event sequence ({journal.length} events)</summary>
                  <ol>
                    {journal.map((event, index) => (
                      <li
                        key={`${event.index}-${event.time_ms}`}
                        className={index === eventIndex ? 'active' : ''}
                      >
                        <button
                          onClick={() => {
                            setPlaying(false);
                            setEventIndex(index);
                          }}
                        >
                          <span>{String(index + 1).padStart(2, '0')}</span>
                          <strong>{event.kind.replaceAll('_', ' ')}</strong>
                          <small>{new Date(event.time_ms).toLocaleTimeString()}</small>
                        </button>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

export function Observatory() {
  const [screen, setScreen] = useState<Screen>('network');
  const [modelId, setModelId] = useState('');
  const [sampleIndex, setSampleIndex] = useState(0);
  const [simulationId, setSimulationId] = useState('');
  const data = useQuery({
    queryKey: ['observatory'],
    queryFn: () => api<ObservatoryData>('/arena/observatory'),
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: false,
  });
  const currentModelId =
    data.data?.network_models.find((model) => model.model_id === modelId)?.model_id ??
    data.data?.network_models[0]?.model_id ??
    '';
  const network = useQuery({
    queryKey: ['observatory-network', currentModelId, sampleIndex],
    queryFn: () =>
      api<NetworkData>(
        `/arena/observatory/models/${currentModelId}/network?sample_index=${sampleIndex}`,
      ),
    enabled: screen === 'network' && !!currentModelId,
    retry: false,
  });
  useEffect(() => {
    if (currentModelId && currentModelId !== modelId) {
      setModelId(currentModelId);
      setSampleIndex(0);
    }
  }, [currentModelId, modelId]);

  return (
    <div className="intelligence-observatory">
      <div className="obs-masthead">
        <div className="obs-title-block">
          <div className="obs-pretitle">
            <span className="obs-instrument-mark">
              <i />
              <i />
              <i />
            </span>{' '}
            MIDAS RESEARCH SYSTEM <b> / </b> INTELLIGENCE OBSERVATORY
          </div>
          <h1>
            Inside the <em>machine.</em>
          </h1>
          <p>
            See how MIDAS trains, tests, and connects its research — using the evidence already
            saved by the system.
          </p>
        </div>
        <div className="obs-masthead-state">
          <span className="obs-live-sigil">
            <i />
            <i />
            <i />
          </span>
          <div>
            <span>RESEARCH RECORDS</span>
            <strong>
              {data.data?.active_training_records
                ? `${data.data.active_training_records} job${data.data.active_training_records === 1 ? '' : 's'} active`
                : 'Standing by'}
            </strong>
            <small>
              {data.data
                ? `Updated ${new Date(data.data.generated_at * 1000).toLocaleTimeString()}`
                : 'Connecting to Arena'}
            </small>
          </div>
          <ShieldCheck size={17} />
        </div>
      </div>
      <div className="obs-boundary-strip">
        <ShieldCheck size={15} />
        <span>
          <strong>Evidence first.</strong> Neural weights, training curves, and research links come
          from saved artifacts. Simulation results are labeled synthetic; public observations stay
          separate.
        </span>
        <span className="obs-read-only">READ ONLY</span>
      </div>
      <details className="obs-reader-guide">
        <summary>New to the Observatory? What these screens show</summary>
        <div>
          <p>
            Start with How it learns to see saved training results, then use Research universe to
            follow models back to their data. Simulations lets you inspect one saved virtual run.
          </p>
          <p>
            A model score or successful simulator check does not show that a model would work in a
            live market. The screens here read saved research records and place no orders.
          </p>
        </div>
      </details>
      <nav className="obs-screen-tabs" aria-label="Observatory views">
        {screenTabs.map(({ id, label, detail, icon: Icon }) => (
          <button key={id} className={screen === id ? 'active' : ''} onClick={() => setScreen(id)}>
            <Icon size={17} />
            <span>
              <strong>{label}</strong>
              <small>{detail}</small>
            </span>
            {screen === id && <i />}
          </button>
        ))}
      </nav>
      {data.isLoading && (
        <div className="obs-page-loading">
          <span className="obs-loader-orbit" />
          <h2>Mapping the research system</h2>
          <p>Reading a bounded index of saved models, evaluations, and findings.</p>
        </div>
      )}
      {data.isError && (
        <div className="obs-error-state">
          <CircleHelp size={26} />
          <h2>The Observatory could not reach Arena</h2>
          <p>{data.error.message}. Existing research artifacts have not been changed.</p>
          <button className="obs-action-button" onClick={() => void data.refetch()}>
            Retry connection
          </button>
        </div>
      )}
      {data.data && (
        <>
          <div className="obs-screen-content">
            {screen === 'network' && (
              <>
                <div className="obs-screen-heading">
                  <div>
                    <span className="obs-section-kicker">
                      <Network size={14} /> WEIGHTED FORWARD PASS
                    </span>
                    <h2>A real neural network, one signal at a time.</h2>
                    <p>
                      Inspect the saved layers and watch a validation example move through actual
                      learned connections.
                    </p>
                  </div>
                  <div className="obs-model-choice">
                    <label htmlFor="obs-model">Trained model</label>
                    <select
                      id="obs-model"
                      value={currentModelId}
                      onChange={(event) => {
                        setModelId(event.target.value);
                        setSampleIndex(0);
                      }}
                    >
                      <optgroup label="Arena MLP models">
                        {data.data.network_models.slice(0, 60).map((model) => (
                          <option key={model.model_id} value={model.model_id}>
                            {model.model_id.slice(-8)} ·{' '}
                            {model.configuration.hidden_size
                              ? `${model.configuration.hidden_size} wide`
                              : model.state}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                  </div>
                </div>
                {network.isLoading && (
                  <div className="obs-page-loading compact">
                    <span className="obs-loader-orbit" />
                    <p>Verifying the model artifact and computing its saved forward pass…</p>
                  </div>
                )}
                {network.isError && (
                  <div className="obs-error-state compact">
                    <h3>Network weights unavailable</h3>
                    <p>{network.error.message}</p>
                    <button className="obs-action-button" onClick={() => void network.refetch()}>
                      Try again
                    </button>
                  </div>
                )}
                {network.data && (
                  <NetworkExplorer
                    key={network.data.model.model_id}
                    data={network.data}
                    models={data.data.network_models}
                    onSampleChange={setSampleIndex}
                  />
                )}
                {!data.data.network_models.length && !network.isLoading && (
                  <div className="obs-empty-state">
                    <Network size={28} />
                    <h3>No inspectable MLP model is saved</h3>
                    <p>
                      The Arena registry has no completed MLP weights that meet the Observatory’s
                      read and verification bounds.
                    </p>
                  </div>
                )}
              </>
            )}
            {screen === 'learning' && <LearningView data={data.data} />}
            {screen === 'universe' && (
              <ResearchUniverse
                data={data.data}
                onExploreModel={(id) => {
                  setModelId(id);
                  setScreen('network');
                }}
                onExploreSimulation={(id) => {
                  setSimulationId(id);
                  setScreen('simulation');
                }}
              />
            )}
            {screen === 'simulation' && (
              <SimulationView key={simulationId} data={data.data} initialId={simulationId} />
            )}
          </div>
          <footer className="obs-footer">
            <span>MIDAS / INTELLIGENCE OBSERVATORY</span>
            <span>
              {data.data.graph.nodes.length} artifacts in the current view · refreshes every 30
              seconds · no research controls
            </span>
          </footer>
        </>
      )}
    </div>
  );
}
