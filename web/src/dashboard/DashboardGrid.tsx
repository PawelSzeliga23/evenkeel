/** Plan 9: the Pulpit's tiles in their order, each in its frame; while editing they can be dragged, removed and set. */
import {
  DndContext, KeyboardSensor, PointerSensor, TouchSensor, closestCenter, useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, rectSortingStrategy, sortableKeyboardCoordinates, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { ReactNode } from "react";
import type { Summary } from "../api/types";
import { CloseIcon, SettingsIcon } from "../shell/icons";
import styles from "./Dashboard.module.css";
import { KINDS, moveTile, removeTile, updateTile, type DashboardLayout, type Tile } from "./layout";
import { TileSettings } from "./TileSettings";
import { AllocationTile, MoversTile, PriceChartTile, ValueChartTile } from "./tiles/ChartTiles";
import { HoldingsTile, IncomeTile, LimitsTile, ReviewTile, SimulatorTile, TagsTile } from "./tiles/CardTiles";
import { AnalysisTile, MetricTile, SummaryTile } from "./tiles/FigureTiles";

export function TileView({ tile, summary }: { tile: Tile; summary: Summary }): ReactNode {
  switch (tile.kind) {
    case "summary": return <SummaryTile tile={tile} summary={summary} />;
    case "metric": return <MetricTile tile={tile} summary={summary} />;
    case "value_chart": return <ValueChartTile tile={tile} summary={summary} />;
    case "price_chart": return <PriceChartTile tile={tile} />;
    case "allocation": return <AllocationTile tile={tile} summary={summary} />;
    case "analysis": return <AnalysisTile tile={tile} summary={summary} />;
    case "limits": return <LimitsTile />;
    case "movers": return <MoversTile tile={tile} summary={summary} />;
    case "holdings": return <HoldingsTile />;
    case "income": return <IncomeTile />;
    case "tags": return <TagsTile />;
    case "simulator": return <SimulatorTile />;
    case "review": return <ReviewTile />;
  }
}

export function DashboardGrid({ layout, summary }: { layout: DashboardLayout; summary: Summary }) {
  return (
    <div className={styles.tileGrid}>
      {layout.tiles.map((tile) => (
        <div key={tile.id} className={styles.tileBox} data-kind={tile.kind} data-size={tile.size}>
          <TileView tile={tile} summary={summary} />
        </div>
      ))}
    </div>
  );
}

function EditableTile({ tile, index, count, summary, configuring, onConfigure, layout, onChange }: {
  tile: Tile; index: number; count: number; summary: Summary; configuring: boolean;
  onConfigure: (id: string | null) => void; layout: DashboardLayout; onChange: (next: DashboardLayout) => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: tile.id });
  const name = KINDS[tile.kind].name;
  return (
    <div ref={setNodeRef} className={styles.tileBox} data-kind={tile.kind} data-size={tile.size} data-editing
      data-dragging={isDragging || undefined} data-configuring={configuring || undefined} role="group" aria-label={`Kafelek ${name}`}
      style={{ transform: CSS.Translate.toString(transform), transition }} {...(configuring ? {} : listeners)}>
      <div className={styles.tileTools}>
        <button type="button" className={styles.tileTool} aria-label={`Usuń kafelek ${name}`}
          onClick={() => onChange(removeTile(layout, tile.id))}><CloseIcon /></button>
        <button ref={setActivatorNodeRef} type="button" className={styles.tileHandle} {...attributes}
          aria-label={`Przeciągnij kafelek ${name}`}>⠿</button>
        <button type="button" className={styles.tileTool} aria-label={`Ustaw kafelek ${name}`} aria-expanded={configuring}
          onClick={() => onConfigure(configuring ? null : tile.id)}><SettingsIcon /></button>
      </div>
      {configuring ? (
        <TileSettings tile={tile} isFirst={index === 0} isLast={index === count - 1}
          onChange={(patch) => onChange(updateTile(layout, tile.id, patch))}
          onMove={(step) => onChange(moveTile(layout, tile.id, index + step))}
          onClose={() => onConfigure(null)} />
      ) : (
        <div className={styles.tileFrozen} inert>
          <TileView tile={tile} summary={summary} />
        </div>
      )}
    </div>
  );
}

/** Mouse: a drag starts after 5 px; finger: after holding 200 ms (a quick swipe scrolls the page); keyboard too. */
export function EditableGrid({ layout, summary, onChange, configuring, onConfigure }: {
  layout: DashboardLayout; summary: Summary; onChange: (next: DashboardLayout) => void;
  configuring: string | null; onConfigure: (id: string | null) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    onChange(moveTile(layout, String(active.id), layout.tiles.findIndex((t) => t.id === over.id)));
  }
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={layout.tiles.map((t) => t.id)} strategy={rectSortingStrategy}>
        <div className={styles.tileGrid} data-editing>
          {layout.tiles.map((tile, index) => (
            <EditableTile key={tile.id} tile={tile} index={index} count={layout.tiles.length} summary={summary}
              configuring={configuring === tile.id} onConfigure={onConfigure} layout={layout} onChange={onChange} />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
