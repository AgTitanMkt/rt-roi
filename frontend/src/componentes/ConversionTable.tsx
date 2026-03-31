import React from "react";

interface ConversionMetric {
  name: string;
  initiate_checkout: number;
  purchase: number;
  checkout_conversion: number;
}

interface ConversionTableProps {
  title: string;
  data: ConversionMetric[];
  isLoading?: boolean;
  emptyMessage?: string;
}

const ConversionTable: React.FC<ConversionTableProps> = ({
  title,
  data,
  isLoading = false,
  emptyMessage = "Sem dados disponíveis",
}) => {
  const getConversionColor = (rate: number): string => {
    if (rate >= 30) return "#22c55e"; // verde
    if (rate >= 20) return "#eab308"; // amarelo
    if (rate >= 10) return "#f97316"; // laranja
    return "#ef4444"; // vermelho
  };

  return (
    <div className="conversionTableContainer">
      <h3 className="conversionTableTitle">{title}</h3>
      
      {isLoading ? (
        <div className="conversionTableLoading">Carregando...</div>
      ) : data.length === 0 ? (
        <div className="conversionTableEmpty">{emptyMessage}</div>
      ) : (
        <table className="conversionTable">
          <thead>
            <tr>
              <th>Nome</th>
              <th>IC</th>
              <th>Compras</th>
              <th>Conv. %</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => (
              <tr key={index}>
                <td className="conversionTableName">{item.name}</td>
                <td className="conversionTableNumber">{item.initiate_checkout.toLocaleString()}</td>
                <td className="conversionTableNumber">{item.purchase.toLocaleString()}</td>
                <td 
                  className="conversionTableRate"
                  style={{ color: getConversionColor(item.checkout_conversion) }}
                >
                  {item.checkout_conversion.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ConversionTable;
