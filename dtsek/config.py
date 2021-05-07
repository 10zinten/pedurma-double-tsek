from pathlib import Path


class BaseConfig:
    def __init__(self):
        self.ocr_path = Path("../archive")
        self.op_pechas_path = Path.home() / ".openpecha" / "pechas"

        # peydurma data path
        self.peydurma_path = Path("data/peydurma")
        self.template_path = self.peydurma_path / "templates"

        # output_path
        self.output_path = Path("./output")

        # annotation
        self.double_tsek_sym = "$"
        self.tsek = "་"
        self.shed = "།"

        # image
        self.img_size = (3969, 2641)

        # dev
        self.debug = False


class KangyurConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self.name = "kangyur"
        self.work_id = "W1PD96682"
        self.d_pecha_id = "P000001"
        self.p_pecha_id = "P000793"
        self.images_path = self.ocr_path / "images" / self.work_id
        self.ocr_output_path = self.ocr_path / " output" / self.work_id
        self.pedurma_output_path = self.output_path / self.name / "pedurma"
        self.dergey_output_path = self.output_path / self.name / "dergey"
        self.pedurma_output_path.mkdir(exist_ok=True, parents=True)
        self.dergey_output_path.mkdir(exist_ok=True, parents=True)


class TengyurConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self.name = "tengyur"
        self.work_id = "W1PD95844"
        self.d_pecha_id = "P000002"
        self.p_pecha_id = "P000791"
        self.images_path = self.ocr_path / "images" / self.work_id
        self.ocr_output_path = self.ocr_path / "output" / self.work_id
        self.pedurma_output_path = self.output_path / self.name / "pedurma"
        self.dergey_output_path = self.output_path / self.name / "dergey"
        self.pedurma_output_path.mkdir(exist_ok=True, parents=True)
        self.dergey_output_path.mkdir(exist_ok=True, parents=True)
