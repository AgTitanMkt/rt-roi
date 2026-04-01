import { createContext } from "react";
import type { FilterContextType } from "./filterContextTypes";

/**
 * FilterContext: Context criado separadamente para evitar react-refresh issues
 */
export const FilterContext = createContext<FilterContextType | undefined>(undefined);

