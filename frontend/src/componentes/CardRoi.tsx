import "../App.css";

interface valueCardProps{
  nome:string, 
  valor:number,
  data:number,
  categoria:number,
  tendencia:"baixa" | "alta",
}

function CardRoi({ nome, valor, data, categoria, tendencia }: valueCardProps) {
  const isDown = tendencia === "baixa";

  return (
    <div className="CardInfo">
      <div className="cardHeader">
        <span className="nameInfo">{nome}</span>
        <span className={`trendBadge ${isDown ? "cor-alerta" : "cor-sucesso"}`}>
          {isDown ? "▼" : "▲"} {categoria}%
        </span>
      </div>
      <div className="valorInfo">{valor.toFixed(2)}x</div>
      <div className="dataInfo">
        <span className="dataLabel">Ontem</span>
        <span className="dataValue">{data.toFixed(2)}x</span>
      </div>
    </div>
  );
}

export default CardRoi;
