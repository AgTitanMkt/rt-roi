import { useContext } from "react";
import { FilterContext } from "./filterContextObject";
import type { FilterContextType } from "./filterContextTypes";

/**
 * Hook para consumir o contexto de filtros
 */
export const useFilters = (): FilterContextType => {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error("useFilters deve ser usado dentro de FilterProvider");
  }
  return context;
};

