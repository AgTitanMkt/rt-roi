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
  const roiToPercent = (input: number) => (input * 100).toFixed(2);

  return (
    <div className="CardInfo">
      <div className="cardHeader">
        <span className="nameInfo">{nome}</span>
        <span className={`trendBadge ${isDown ? "cor-alerta" : "cor-sucesso"}`}>
          {isDown ? "▼" : "▲"} {categoria}%
        </span>
      </div>
      <div className="valorInfo">{roiToPercent(valor)}%</div>
      <div className="dataInfo">
        <span className="dataLabel">Ontem</span>
        <span className="dataValue">{roiToPercent(data)}%</span>
      </div>
    </div>
  );
}

export default CardRoi;
