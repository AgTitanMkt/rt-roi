import React from "react";
import { useFilters } from "../context/useFilters";
import type { Filters } from "../context/filterContextTypes";
import { PERIOD_OPTIONS, SQUAD_OPTIONS, CHECKOUT_OPTIONS, PRODUCT_OPTIONS } from "../utils/filterOptions";
import "./FilterBar.css";


/**
 * FilterBar: Componente centralizado de filtros
 * Reutilizável em qualquer página
 */
interface FilterBarProps {
  compact?: boolean; // Se true, mostra versão compacta
  showAdvanced?: boolean; // Se true, mostra filtros avançados
  onFiltersChange?: (filters: Filters) => void; // Callback opcional
}

export const FilterBar: React.FC<FilterBarProps> = ({
  compact = false,
  showAdvanced = false,
  onFiltersChange,
}) => {
  const { filters, updateFilter, resetFilters, chartComparison, updateChartComparison, resetChartComparison } = useFilters();

  const handlePeriodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const period = e.target.value as Filters["period"];
    updateFilter("period", period);
    onFiltersChange?.({ ...filters, period });
  };

  const handleSquadChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const squad = e.target.value || undefined;
    updateFilter("squad", squad);
    onFiltersChange?.({ ...filters, squad });
  };

  const handleCheckoutChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const checkout = e.target.value || undefined;
    updateFilter("checkout", checkout);
    onFiltersChange?.({ ...filters, checkout });
  };

  const handleProductChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const product = e.target.value || undefined;
    updateFilter("product", product);
    onFiltersChange?.({ ...filters, product });
  };

  const handleOfferChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const offer = e.target.value || undefined;
    updateFilter("offer", offer);
    onFiltersChange?.({ ...filters, offer });
  };

  const handleReset = () => {
    resetFilters();
    resetChartComparison();
    onFiltersChange?.({ period: "24h" });
  };

  const handleCompareEnabledChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateChartComparison("enabled", e.target.checked);
  };

  const handleBaseDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.value) return;
    updateChartComparison("base_date", e.target.value);
  };

  const handleCompareDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.value) return;
    updateChartComparison("compare_date", e.target.value);
  };

  if (compact) {
    return (
      <div className="filterBar filterBar--compact">
        <div className="filterBar__group">
          <label htmlFor="period-select" className="filterBar__label">
            Período:
          </label>
          <select
            id="period-select"
            value={filters.period}
            onChange={handlePeriodChange}
            className="filterBar__select"
          >
            {PERIOD_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filterBar__group">
          <label htmlFor="squad-select" className="filterBar__label">
            Squad:
          </label>
          <select
            id="squad-select"
            value={filters.squad || ""}
            onChange={handleSquadChange}
            className="filterBar__select"
          >
            {SQUAD_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleReset} className="filterBar__reset">
          Limpar
        </button>
      </div>
    );
  }

  return (
    <div className="filterBar">
      <div className="filterBar__container">
        {/* Linha 1: Filtros principais */}
        <div className="filterBar__row">
          <div className="filterBar__group">
            <label htmlFor="period-select" className="filterBar__label">
              Período
            </label>
            <select
              id="period-select"
              value={filters.period}
              onChange={handlePeriodChange}
              className="filterBar__select"
            >
              {PERIOD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="filterBar__group">
            <label htmlFor="squad-select" className="filterBar__label">
              Squad
            </label>
            <select
              id="squad-select"
              value={filters.squad || ""}
              onChange={handleSquadChange}
              className="filterBar__select"
            >
              {SQUAD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

           <div className="filterBar__group">
             <label htmlFor="checkout-select" className="filterBar__label">
               Checkout
             </label>
             <select
               id="checkout-select"
               value={filters.checkout || ""}
               onChange={handleCheckoutChange}
               className="filterBar__select"
             >
               {CHECKOUT_OPTIONS.map((opt) => (
                 <option key={opt.value} value={opt.value}>
                   {opt.label}
                 </option>
               ))}
             </select>
           </div>

           <div className="filterBar__group">
             <label htmlFor="product-select" className="filterBar__label">
               Produto
             </label>
             <select
               id="product-select"
               value={filters.product || ""}
               onChange={handleProductChange}
               className="filterBar__select"
             >
               {PRODUCT_OPTIONS.map((opt) => (
                 <option key={opt.value} value={opt.value}>
                   {opt.label}
                 </option>
               ))}
             </select>
           </div>

           <button onClick={handleReset} className="filterBar__reset">
             Limpar Filtros
           </button>
         </div>

         <div className="filterBar__row filterBar__row--advanced">
           <div className="filterBar__group filterBar__group--checkbox">
             <label htmlFor="compare-enabled" className="filterBar__label">
               Comparar gráficos
             </label>
             <input
               id="compare-enabled"
               type="checkbox"
               checked={chartComparison.enabled}
               onChange={handleCompareEnabledChange}
               className="filterBar__checkbox"
             />
           </div>

           <div className="filterBar__group">
             <label htmlFor="compare-base-date" className="filterBar__label">
               Dia base
             </label>
             <input
               id="compare-base-date"
               type="date"
               value={chartComparison.base_date}
               onChange={handleBaseDateChange}
               className="filterBar__input"
             />
           </div>

           <div className="filterBar__group">
             <label htmlFor="compare-target-date" className="filterBar__label">
               Comparar com
             </label>
             <input
               id="compare-target-date"
               type="date"
               value={chartComparison.compare_date}
               onChange={handleCompareDateChange}
               className="filterBar__input"
             />
           </div>
         </div>

         {/* Linha 2: Filtros avançados (opcional) */}
         {showAdvanced && (
           <div className="filterBar__row filterBar__row--advanced">
             <div className="filterBar__group">
               <label htmlFor="offer-input" className="filterBar__label">
                 Oferta ID
               </label>
               <input
                 id="offer-input"
                 type="text"
                 placeholder="Ex: 12345"
                 value={filters.offer || ""}
                 onChange={handleOfferChange}
                 className="filterBar__input"
               />
             </div>

             {/* Espaço para mais filtros no futuro */}
           </div>
         )}
       </div>
    </div>
  );
};

export default FilterBar;

