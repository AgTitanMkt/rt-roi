import "../App.css";

interface valueCardProps{
  nome:string, 
  valor:number,
  data:number,
  categoria:number,
  tendencia:"baixa" | "alta",
  prefixo?: string,
  sufixo?: string,
  casasDecimais?: number,
  className?: string,
}

function ValorCard({
  nome,
  valor,
  data,
  categoria,
  tendencia,
  prefixo = "$",
  sufixo = "",
  casasDecimais = 2,
  className = "",
}: valueCardProps) {
  const isDown = tendencia === "baixa";

  return (
    <div className={`CardInfo ${className}`.trim()}>
      <div className="cardHeader">
        <span className="nameInfo">{nome}</span>
        <span className={`trendBadge ${isDown ? "cor-alerta" : "cor-sucesso"}`}>
          {isDown ? "▼" : "▲"} {categoria}%
        </span>
      </div>
      <div className="valorInfo">{prefixo}{valor.toFixed(casasDecimais)}{sufixo}</div>
      <div className="dataInfo">
        <span className="dataLabel">Ontem</span>
        <span className="dataValue">{prefixo}{data.toFixed(casasDecimais)}{sufixo}</span>
      </div>
    </div>
  );
}

export default ValorCard;
