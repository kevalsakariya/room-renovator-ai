import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import {
  Select,
  Input,
  Button,
  Typography,
  Switch,
  Layout,
  ConfigProvider,
  theme,
  Row,
  Col,
  Divider,
  Tag,
  Tooltip,
} from "antd";
import { BulbFilled, BulbOutlined } from "@ant-design/icons";
import ImageUpload from "./components/ImageUpload";
import Footer from "./components/Footer";
import MarkdownCard from "./components/MarkdownCard";

const { Header, Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;
const API_BASE_URL = "http://127.0.0.1:8000";

function App() {
  const [homeImage, setHomeImage] = useState(null);
  const [backgroundColor, setBackgroundColor] = useState("#f4ede4");
  const [foregroundColor, setForegroundColor] = useState("#2c3e50");
  const [designType, setDesignType] = useState("interior");
  const [roomType, setRoomType] = useState("living");
  const [style, setStyle] = useState("modern");
  const [history, setHistory] = useState([]);
  const [instructions, setInstructions] = useState("");
  const [backendStatus, setBackendStatus] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem("darkMode");
    return saved ? JSON.parse(saved) : false;
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const resultRef = useRef(null);
  const { defaultAlgorithm, darkAlgorithm } = theme;

  useEffect(() => {
    localStorage.setItem("darkMode", JSON.stringify(isDarkMode));
  }, [isDarkMode]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/status`, { timeout: 3000 });
        setBackendStatus(response.data);
      } catch {
        setBackendStatus({ status: "offline", mode_label: "Backend Offline" });
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [result]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!homeImage) {
      toast.error("Please upload an image of your space first");
      return;
    }
    if (!designType) {
      toast.warning("Please choose Interior or Exterior design type");
      return;
    }
    if (!roomType) {
      toast.warning("Please select a room type");
      return;
    }
    if (!style) {
      toast.warning("Please select a design style");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append("place_image", homeImage);
    formData.append("background_color", backgroundColor);
    formData.append("foreground_color", foregroundColor);
    formData.append("design_type", designType);
    formData.append("room_type", roomType);
    formData.append("style", style);
    formData.append("instructions", instructions);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/try-on`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const newResult = {
        id: Date.now(),
        resultImage: response.data.image,
        text: response.data.text,
        mode: response.data.mode,
        designType,
        roomType,
        style,
        backgroundColor,
        foregroundColor,
        instructions: instructions.trim(),
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setResult(newResult);
      setHistory((prev) => [newResult, ...prev]);

      toast.success("Design generated successfully!");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Design generation failed. Check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  const textColor = isDarkMode ? "#e4e4e4" : "#111827";

  return (
    <ConfigProvider
      theme={{
        algorithm: isDarkMode ? darkAlgorithm : defaultAlgorithm,
        token: {
          colorPrimary: "#0ea5e9",
          borderRadius: 10,
        },
      }}
    >
      <Layout style={{ minHeight: "100vh", background: isDarkMode ? "#0f0f0f" : "#f9fafb" }}>
        <Header
          style={{
            background: "transparent",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "1.5rem 1rem",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <Title level={3} style={{ margin: 0, color: textColor, fontSize: "1.5rem", flex: 1 }}>
            🏡 AI Space Design Studio
          </Title>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
            {backendStatus && (
              <Tooltip
                title={
                  backendStatus.status === "offline"
                    ? "Start backend with: uvicorn main:app --reload in the backend folder"
                    : `Active engine: ${backendStatus.mode_label}`
                }
              >
                <Tag
                  color={
                    backendStatus.status === "offline"
                      ? "error"
                      : backendStatus.active_mode === "colab"
                      ? "success"
                      : backendStatus.active_mode === "local"
                      ? "processing"
                      : "warning"
                  }
                  style={{
                    fontSize: 12,
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontWeight: 500,
                  }}
                >
                  ● {backendStatus.mode_label || "Backend Offline"}
                </Tag>
              </Tooltip>
            )}
            <Switch
              checked={isDarkMode}
              onChange={setIsDarkMode}
              checkedChildren={<BulbFilled />}
              unCheckedChildren={<BulbOutlined />}
            />
          </div>
        </Header>

        <Content style={{ padding: "2rem 1rem" }}>
          <div style={{ maxWidth: "1200px", margin: "0 auto", width: "100%" }}>
            <Title level={2} style={{ color: textColor, textAlign: "center", marginBottom: "2rem" }}>
              Envision Your Space, Reimagined
            </Title>
            <Text
              style={{
                display: "block",
                color: textColor,
                textAlign: "center",
                maxWidth: 720,
                margin: "-1rem auto 2rem",
                opacity: 0.8,
              }}
            >
              Transform a photo into a personalized interior or exterior concept, guided by your
              preferred style, colors, and design details.
            </Text>

            {/* FORM */}
            <form onSubmit={handleSubmit}>
              <Row gutter={[24, 24]} justify="center" style={{ flexWrap: "wrap" }}>
                <Col xs={24} sm={24} md={24} lg={12}>
                  <ImageUpload
                    label="Upload Space Photo"
                    onImageChange={setHomeImage}
                    isDarkMode={isDarkMode}
                  />
                </Col>

                <Col xs={24} sm={24} md={24} lg={12}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <div>
                      <Text style={{ color: textColor }}>Design Type</Text>
                      <Select
                        placeholder="Interior or Exterior?"
                        style={{ width: "100%", marginTop: 4 }}
                        value={designType || undefined}
                        onChange={setDesignType}
                      >
                        <Option value="interior">Interior</Option>
                        <Option value="exterior">Exterior</Option>
                      </Select>
                    </div>

                    <div>
                      <Text style={{ color: textColor }}>Room Type</Text>
                      <Select
                        placeholder="Select room type"
                        style={{ width: "100%", marginTop: 4 }}
                        value={roomType || undefined}
                        onChange={setRoomType}
                      >
                        <Option value="living">Living Room</Option>
                        <Option value="bedroom">Bedroom</Option>
                        <Option value="kitchen">Kitchen</Option>
                        <Option value="bathroom">Bathroom</Option>
                        <Option value="balcony">Balcony</Option>
                        <Option value="garden">Garden</Option>
                      </Select>
                    </div>

                    <div>
                      <Text style={{ color: textColor }}>Design Style</Text>
                      <Select
                        placeholder="Select a style"
                        style={{ width: "100%", marginTop: 4 }}
                        value={style || undefined}
                        onChange={setStyle}
                      >
                        <Option value="modern">Modern</Option>
                        <Option value="minimalist">Minimalist</Option>
                        <Option value="rustic">Rustic</Option>
                        <Option value="bohemian">Bohemian</Option>
                        <Option value="classic">Classic</Option>
                      </Select>
                    </div>

                    <Row gutter={16}>
                      <Col xs={12}>
                        <Text style={{ color: textColor }}>Backdrop Color</Text>
                        <Input
                          type="color"
                          value={backgroundColor}
                          onChange={(e) => setBackgroundColor(e.target.value)}
                          style={{
                            width: "100%",
                            height: "48px",
                            padding: "6px",
                            borderRadius: 8,
                            cursor: "pointer",
                          }}
                        />
                      </Col>
                      <Col xs={12}>
                        <Text style={{ color: textColor }}>Accent Color</Text>
                        <Input
                          type="color"
                          value={foregroundColor}
                          onChange={(e) => setForegroundColor(e.target.value)}
                          style={{
                            width: "100%",
                            height: "48px",
                            padding: "6px",
                            borderRadius: 8,
                            cursor: "pointer",
                          }}
                        />
                      </Col>
                    </Row>
                  </div>
                </Col>
              </Row>

              <div style={{ marginTop: 32 }}>
                <Text style={{ color: textColor }}>Additional Styling Preferences</Text>
                <Input.TextArea
                  rows={4}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  style={{ width: "100%", marginTop: 8 }}
                  placeholder="Example: Warm ambient lighting, indoor plants, hardwood floors, open concept shelving..."
                />
              </div>

              <div style={{ textAlign: "center", marginTop: 40 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  loading={loading}
                  style={{ width: 220, height: 48, fontSize: 16, fontWeight: 600 }}
                >
                  {loading ? "Transforming Space..." : "Generate Makeover"}
                </Button>
              </div>
            </form>

            {/* RESULT */}
            {result && (
              <div ref={resultRef} style={{ marginTop: 64, textAlign: "center" }}>
                <Divider />
                <Title level={3} style={{ color: textColor, marginBottom: 8 }}>
                  Your AI-Designed Space
                </Title>
                <img
                  src={result.resultImage}
                  alt="AI Design Result"
                  style={{
                    width: "100%",
                    maxWidth: "720px",
                    maxHeight: "600px",
                    objectFit: "contain",
                    borderRadius: 16,
                    boxShadow: "0 8px 30px rgba(0,0,0,0.2)",
                    margin: "16px auto 24px",
                    display: "block",
                  }}
                />
                {result.text && (
                  <MarkdownCard text={result.text} isDarkMode={isDarkMode} />
                )}
              </div>
            )}

            {/* HISTORY */}
            {history.length > 0 && (
              <div style={{ marginTop: 80 }}>
                <Divider />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                  <Title level={3} style={{ color: textColor, margin: 0 }}>
                    Previous Makeovers ({history.length})
                  </Title>
                  <Button
                    size="small"
                    danger
                    onClick={() => setHistory([])}
                    style={{ borderRadius: 6 }}
                  >
                    Clear History
                  </Button>
                </div>
                <Row gutter={[20, 20]}>
                  {history.map((item) => (
                    <Col xs={24} sm={12} md={8} key={item.id}>
                      <div
                        onClick={() => {
                          setResult(item);
                          resultRef.current?.scrollIntoView({ behavior: "smooth" });
                        }}
                        style={{
                          background: isDarkMode ? "#1f1f1f" : "#ffffff",
                          border: isDarkMode ? "1px solid #2d2d2d" : "1px solid #e5e7eb",
                          padding: 12,
                          borderRadius: 14,
                          boxShadow: "0 4px 14px rgba(0,0,0,0.06)",
                          display: "flex",
                          flexDirection: "column",
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = "translateY(-3px)";
                          e.currentTarget.style.boxShadow = "0 8px 24px rgba(0,0,0,0.12)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = "none";
                          e.currentTarget.style.boxShadow = "0 4px 14px rgba(0,0,0,0.06)";
                        }}
                      >
                        <div style={{ position: "relative", overflow: "hidden", borderRadius: 10 }}>
                          <img
                            src={item.resultImage}
                            alt="Previous Makeover"
                            style={{
                              width: "100%",
                              height: "200px",
                              objectFit: "cover",
                              display: "block",
                              borderRadius: 10,
                            }}
                          />
                          {item.instructions && (
                            <div
                              style={{
                                position: "absolute",
                                bottom: 0,
                                left: 0,
                                right: 0,
                                background: "rgba(15, 23, 42, 0.88)",
                                backdropFilter: "blur(4px)",
                                padding: "6px 10px",
                                color: "#f8fafc",
                                fontSize: 11,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              ✍️ {item.instructions}
                            </div>
                          )}
                        </div>

                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10 }}>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {item.roomType && (
                              <Tag color="cyan" style={{ margin: 0, textTransform: "capitalize", fontSize: 11 }}>
                                {item.roomType}
                              </Tag>
                            )}
                            {item.style && (
                              <Tag color="purple" style={{ margin: 0, textTransform: "capitalize", fontSize: 11 }}>
                                {item.style}
                              </Tag>
                            )}
                          </div>
                          {item.backgroundColor && item.foregroundColor && (
                            <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                              <span
                                title={`Backdrop: ${item.backgroundColor}`}
                                style={{
                                  width: 14,
                                  height: 14,
                                  borderRadius: "50%",
                                  backgroundColor: item.backgroundColor,
                                  border: "1px solid rgba(255,255,255,0.4)",
                                  display: "inline-block",
                                }}
                              />
                              <span
                                title={`Accent: ${item.foregroundColor}`}
                                style={{
                                  width: 14,
                                  height: 14,
                                  borderRadius: "50%",
                                  backgroundColor: item.foregroundColor,
                                  border: "1px solid rgba(255,255,255,0.4)",
                                  display: "inline-block",
                                }}
                              />
                            </div>
                          )}
                        </div>

                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginTop: 10,
                            paddingTop: 8,
                            borderTop: `1px solid ${isDarkMode ? "#27272a" : "#f1f5f9"}`,
                          }}
                        >
                          <Text style={{ color: isDarkMode ? "#a1a1aa" : "#64748b", fontSize: 11 }}>
                            🕒 {item.timestamp}
                          </Text>
                          <Text style={{ color: "#0ea5e9", fontSize: 12, fontWeight: 500 }}>
                            View in Studio →
                          </Text>
                        </div>
                      </div>
                    </Col>
                  ))}
                </Row>
              </div>
            )}
          </div>
        </Content>

        <Footer isDarkMode={isDarkMode} />
        <ToastContainer theme={isDarkMode ? "dark" : "light"} />
      </Layout>
    </ConfigProvider>
  );
}

export default App;