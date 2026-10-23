import os
from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.programming.language import Python
from diagrams.onprem.database import MySQL
from diagrams.onprem.client import Users
from diagrams.saas.analytics import Stitch

graph_attr = {
    "fontsize": "16",
    "bgcolor": "#0B0F19",
    "fontcolor": "#FFFFFF",
    "pad": "0.5",
}
node_attr = {
    "fontcolor": "#FFFFFF",
    "fontsize": "11",
}
edge_attr = {
    "color": "#3B82F6",
    "penwidth": "1.5",
}

with Diagram(
    "CIP Forsta ETL Pipeline Architecture",
    filename="reports/forsta_etl_diagram",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    source = Users("400 Consumers\n(Weekly CSI-US Wave)")

    with Cluster("Extraction Layer (Zero Point)", graph_attr={"bgcolor": "#111827", "fontcolor": "#06B6D4"}):
        api = Python("Forsta Client\n(GET API / x-apikey)")
        reg = MySQL("Survey Register\n(cip_forsta_survey)")
        pii = Python("PII Filter & HMAC\n(HMAC-SHA256 RID)")

    with Cluster("Transformation Layer", graph_attr={"bgcolor": "#111827", "fontcolor": "#8B5CF6"}):
        datamap = Python("Datamap Decompose\n(Questions & Options)")
        verify = Python("Verification Gate\n(100% Parity Reconcile)")
        profile = Python("Demographics Profiler\n(12 Standard Cohorts)")
        cube = Python("OLAP Cube Engine\n(Contingency Tables)")

    with Cluster("Loading & Serving Layer", graph_attr={"bgcolor": "#111827", "fontcolor": "#10B981"}):
        db = MySQL("Warehouse Tables\n(cip_respondent, answer)")
        cubedb = MySQL("Serving Cubes\n(cip_crosstab_cube)")
        api_srv = Python("FastAPI Portal\n(Port 8000 / Tunnel)")

    source >> Edge(label="Fieldwork (13h)") >> api
    api >> Edge(label="400 Quota Check") >> reg
    api >> Edge(label="Raw JSON") >> pii
    pii >> datamap >> verify >> profile >> cube
    verify >> db
    cube >> cubedb
    cubedb >> api_srv
    db >> api_srv

print("Pipeline diagram script executed successfully.")
