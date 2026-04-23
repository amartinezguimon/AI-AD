import { Composition } from "remotion";
import { VisionMetricsVideo } from "./Video";

export const RemotionRoot = () => {
  return (
    <Composition
      id="VisionMetrics"
      component={VisionMetricsVideo}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
