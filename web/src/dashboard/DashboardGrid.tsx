/** Plan 9: the Pulpit's tiles in their order, each in its frame. */
import type { ReactNode } from "react";
import type { Summary } from "../api/types";
import styles from "./Dashboard.module.css";
import type { DashboardLayout, Tile } from "./layout";
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
